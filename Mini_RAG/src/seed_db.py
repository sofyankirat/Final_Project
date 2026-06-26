import asyncio
import os
import sys
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker

# Add current folder to sys.path so we can import helpers and models
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from helpers.config import get_settings
from models.ProjectModel import ProjectModel
from models.AssetModel import AssetModel
from models.ChunkModel import ChunkModel
from models.db_schemas import Project, Asset, DataChunk
from models.enums.AssetTypeEnums import AssetTypeEnums
from controllers import ProcessController, NLPController
from stores.llm.LLMProviderFactory import LLMProviderFactory
from stores.vectordb.VectorDBProviderFactory import VectorDBProviderFactory
from stores.llm.templates.template_parser import TemplateParser

async def main():
    settings = get_settings()
    
    print("Connecting to database...")
    postgres_conn = f"postgresql+asyncpg://{settings.POSTGRES_USERNAME}:{settings.POSTGRES_PASSWORD}@{settings.POSTGRES_HOST}:{settings.POSTGRES_PORT}/{settings.POSTGRES_MAIN_DATABASE}"
    engine = create_async_engine(postgres_conn)
    db_client = sessionmaker(
        engine, class_=AsyncSession, expire_on_commit=False
    )
    
    # Initialize templates
    template_parser = TemplateParser(
        language=settings.PRIMARY_LANG,
        default_language=settings.DEFAULT_LANG,
    )
    
    # Initialize factories and clients
    llm_provider_factory = LLMProviderFactory(settings, template_parser)
    vectordb_provider_factory = VectorDBProviderFactory(config=settings, db_client=db_client)
    
    generation_provider = settings.GENERATION_BACKEND
    generation_client = llm_provider_factory.create(provider=generation_provider)
    generation_client.set_generation_model(model_id=settings.GENERATION_MODEL_ID)
    
    embedding_client = llm_provider_factory.create(provider=settings.EMBEDDING_BACKEND)
    embedding_client.set_embedding_model(model_id=settings.EMBEDDING_MODEL_ID,
                                         embedding_size=settings.EMBEDDING_MODEL_SIZE)
    
    vectordb_client = vectordb_provider_factory.create(provider=settings.VECTOR_DB_BACKEND)
    await vectordb_client.connect()
    
    # Initialize controllers
    nlp_controller = NLPController(
        vectordb_client=vectordb_client,
        generation_client=generation_client,
        embedding_client=embedding_client,
        template_parser=template_parser,
        provider=generation_provider
    )
    
    project_model = await ProjectModel.create_instance(db_client=db_client)
    asset_model = await AssetModel.create_instance(db_client=db_client)
    chunk_model = await ChunkModel.create_instance(db_client=db_client)
    
    project_id = 1
    project = await project_model.get_project_or_create_one(project_id=project_id)
    print(f"Project (ID: {project.project_id}) resolved.")
    
    # Check assets directory for project_id = 1
    assets_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "assets", "files", str(project_id))
    if not os.path.exists(assets_dir):
        print(f"Assets directory not found at {assets_dir}")
        await vectordb_client.disconnect()
        await engine.dispose()
        return
        
    files = [f for f in os.listdir(assets_dir) if os.path.isfile(os.path.join(assets_dir, f))]
    if not files:
        print("No files found to seed.")
        await vectordb_client.disconnect()
        await engine.dispose()
        return
        
    print(f"Found files to seed: {files}")
    
    # For each file, upload, process, and index
    for filename in files:
        file_path = os.path.join(assets_dir, filename)
        file_size = os.path.getsize(file_path)
        
        # Step 1: Check if already registered
        existing_asset = await asset_model.get_asset_record(
            asset_project_id=project.project_id,
            asset_name=filename
        )
        
        if existing_asset:
            print(f"File '{filename}' already registered as asset {existing_asset.asset_id}.")
            asset_record = existing_asset
        else:
            print(f"Registering asset '{filename}'...")
            asset_resource = Asset(
                asset_project_id=project.project_id,
                asset_type=AssetTypeEnums.FILE.value,
                asset_name=filename,
                asset_size=file_size
            )
            asset_record = await asset_model.create_asset(asset=asset_resource)
            print(f"Registered with asset_id: {asset_record.asset_id}")
            
        # Step 2: Process file into chunks
        print(f"Processing '{filename}' into chunks...")
        process_controller = ProcessController(project_id=str(project_id))
        file_content = process_controller.get_file_content(file_id=filename)
        
        if not file_content:
            print(f"Failed to read file content for {filename}.")
            continue
            
        file_chunks = process_controller.process_file_content(
            file_content=file_content,
            file_id=filename,
            chunk_size=100, # Same chunk size as frontend
            overlap_size=20
        )
        
        if not file_chunks:
            print(f"Failed to split file {filename} into chunks.")
            continue
            
        print(f"Split into {len(file_chunks)} chunks.")
        
        # Check if chunks are already in DB
        existing_chunks_count = await chunk_model.get_total_chunks_count(project_id=project.project_id)
        if existing_chunks_count > 0:
            print(f"Project already has {existing_chunks_count} chunks in database. Resetting chunks...")
            # Delete and rebuild to ensure consistency
            collection_name = nlp_controller.create_collection_name(project_id=project.project_id)
            await vectordb_client.delete_collection(collection_name=collection_name)
            await chunk_model.delete_chunks_by_project_id(project_id=project.project_id)
            print("Deleted old chunks and collections.")
            
        file_chunks_records = [
            DataChunk(
                chunk_text=chunk.page_content,
                chunk_metadata=chunk.metadata,
                chunk_order=i+1,
                chunk_project_id=project.project_id,
                chunk_asset_id=asset_record.asset_id
            )
            for i, chunk in enumerate(file_chunks)
        ]
        
        inserted_chunks_count = await chunk_model.insert_many_chunks(chunks=file_chunks_records)
        print(f"Successfully inserted {inserted_chunks_count} chunks into 'chunks' table.")
        
        # Step 3: Index chunks into Vector DB (pgvector)
        print("Embedding and indexing chunks into Vector DB...")
        
        # Re-initialize collection
        collection_name = nlp_controller.create_collection_name(project_id=project.project_id)
        await vectordb_client.create_collection(
            collection_name=collection_name,
            embedding_size=embedding_client.embedding_size,
            do_reset=True
        )
        
        # Mark chunks unindexed first (for safety)
        await chunk_model.reset_chunks_indexed_flag(project_id=project.project_id)
        
        # Index in pages
        page_no = 1
        has_records = True
        indexed_count = 0
        
        while has_records:
            page_chunks = await chunk_model.get_unindexed_project_chunks(
                project_id=project.project_id, page_no=page_no, page_size=20
            )
            
            if not page_chunks:
                has_records = False
                break
                
            chunks_ids = [c.chunk_id for c in page_chunks]
            
            success = await nlp_controller.index_into_vector_db(
                project=project,
                chunks=page_chunks,
                chunks_ids=chunks_ids
            )
            
            if not success:
                print("Failed during vector database indexing step.")
                break
                
            await chunk_model.mark_chunks_as_indexed(chunk_ids=chunks_ids)
            indexed_count += len(page_chunks)
            print(f"Indexed page {page_no} ({len(page_chunks)} chunks). Total indexed so far: {indexed_count}")
            await asyncio.sleep(15)
            
        print(f"Successfully indexed all chunks into pgvector collection '{collection_name}'!")
        
    await vectordb_client.disconnect()
    await engine.dispose()
    print("Database seeding completed successfully!")

if __name__ == "__main__":
    asyncio.run(main())
