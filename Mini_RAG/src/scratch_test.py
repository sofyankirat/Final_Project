import asyncio
import os
import sys
import io

# Setup stdout to use utf-8 so Arabic prints correctly
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from sqlalchemy import text

from helpers.config import get_settings
from models.db_schemas import Project, DataChunk

# Import directly to avoid importing ProcessController and PyTorch
from controllers.NLPController import NLPController
from stores.llm.LLMProviderFactory import LLMProviderFactory
from stores.vectordb.VectorDBProviderFactory import VectorDBProviderFactory
from stores.llm.templates.template_parser import TemplateParser

async def test_search():
    settings = get_settings()
    # Force host to localhost for running on host machine
    settings.POSTGRES_HOST = "localhost"
    
    postgres_conn = f"postgresql+asyncpg://{settings.POSTGRES_USERNAME}:{settings.POSTGRES_PASSWORD}@localhost:{settings.POSTGRES_PORT}/{settings.POSTGRES_MAIN_DATABASE}"
    print(f"Connecting to database at {postgres_conn}...")
    engine = create_async_engine(postgres_conn)
    db_client = sessionmaker(
        engine, class_=AsyncSession, expire_on_commit=False
    )
    
    template_parser = TemplateParser(
        language=settings.PRIMARY_LANG,
        default_language=settings.DEFAULT_LANG,
    )
    
    llm_provider_factory = LLMProviderFactory(settings, template_parser)
    vectordb_provider_factory = VectorDBProviderFactory(config=settings, db_client=db_client)
    
    embedding_client = llm_provider_factory.create(provider=settings.EMBEDDING_BACKEND)
    embedding_client.set_embedding_model(
        model_id=settings.EMBEDDING_MODEL_ID,
        embedding_size=settings.EMBEDDING_MODEL_SIZE
    )
    
    vectordb_client = vectordb_provider_factory.create(provider=settings.VECTOR_DB_BACKEND)
    await vectordb_client.connect()
    
    nlp_controller = NLPController(
        vectordb_client=vectordb_client,
        generation_client=None, # not needed for search
        embedding_client=embedding_client,
        template_parser=template_parser,
        provider=None
    )
    
    # Resolve project_id=1
    project = Project(project_id=1)
    
    # 1. Print total chunks in postgres
    async with db_client() as session:
        result = await session.execute(text("SELECT COUNT(*) FROM chunks WHERE chunk_project_id = 1"))
        count = result.scalar()
        print(f"Total chunks in PostgreSQL chunks table: {count}")
        
        # Print some chunks with distinct metadata
        result = await session.execute(text("SELECT chunk_id, chunk_metadata, SUBSTRING(chunk_text, 1, 100) FROM chunks WHERE chunk_project_id = 1 LIMIT 10"))
        print("\nFirst 10 chunks in PostgreSQL:")
        for r in result:
            print(f"ID: {r[0]}, Metadata: {r[1]}, Text snippet: {repr(r[2])}")
            
    # 2. Search vector DB
    query = "ما هي مواد سنه ثالثه الترم الثاني"
    print(f"\nSearching vector DB for query: '{query}'")
    
    collection_name = nlp_controller.create_collection_name(project_id=str(project.project_id))
    query_vector = await embedding_client.embed_text(text=query, document_type="QUERY")
    
    results = await vectordb_client.search_by_vector(
        collection_name=collection_name,
        vector=query_vector[0],
        limit=5
    )
    
    if not results:
        print("No search results returned.")
    else:
        print(f"\nFound {len(results)} results:")
        for idx, doc in enumerate(results):
            text_val = doc.text
            metadata_val = doc.metadata if hasattr(doc, 'metadata') else {}
            score_val = doc.score if hasattr(doc, 'score') else 'N/A'
            print(f"\nResult #{idx+1} [Score: {score_val}]:")
            print(f"Metadata: {metadata_val}")
            print(f"Content:\n{text_val[:400]}...")
            print("-" * 50)
            
    await vectordb_client.disconnect()
    await engine.dispose()

if __name__ == "__main__":
    asyncio.run(test_search())
