from .BaseController import BaseController
from .ProjectController import ProjectController
from langchain_community.document_loaders import TextLoader, PyMuPDFLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from models import ProcessingEnums
from typing import List
from dataclasses import dataclass
import os
import re
import unicodedata

@dataclass
class Document:
    page_content: str
    metadata: dict

class ProcessController(BaseController):

    def __init__(self, project_id: str):
        super().__init__()

        self.project_id = project_id
        self.project_path = ProjectController().get_project_path(project_id=project_id)

    def get_file_extension(self, file_id: str):
        return os.path.splitext(file_id)[-1]

    def get_file_loader(self, file_id: str):

        file_ext = self.get_file_extension(file_id=file_id)
        file_path = os.path.join(
            self.project_path,
            file_id
        )

        if not os.path.exists(file_path):
            return None

        if file_ext == ProcessingEnums.TXT.value:
            return TextLoader(file_path, encoding="utf-8")

        if file_ext == ProcessingEnums.PDF.value:
            return PyMuPDFLoader(file_path)
        
        return None

    def get_file_content(self, file_id: str):

        loader = self.get_file_loader(file_id=file_id)
        if loader:
            return loader.load()

        return None

    def process_file_content(self, file_content: list, file_id: str,
                            chunk_size: int=1000, overlap_size: int=200):
        
        file_content_texts = [
            unicodedata.normalize('NFKC', rec.page_content)
            for rec in file_content
        ]

        file_content_metadata = [
            rec.metadata
            for rec in file_content
        ]

        if "courses_table" in file_id.lower():
            chunks = self.process_table_splitter(
                texts=file_content_texts,
                metadatas=file_content_metadata,
            )
        else:
            chunks = self.process_simpler_splitter(
                texts=file_content_texts,
                metadatas=file_content_metadata,
                chunk_size=chunk_size,
                overlap_size=overlap_size,
            )

        return chunks

    def extract_metadata_from_header(self, header_line: str) -> dict:
        metadata = {}
        header = header_line.strip()
        if header.startswith("##"):
            header = header[2:].strip()

        match = re.search(r'برنامج\s+([^-]+?)\s*-\s*المستوى\s+(\d+)\s*-\s*الفصل\s+الدراسي\s+(.+)', header)
        if match:
            metadata['program'] = match.group(1).strip()
            metadata['level'] = match.group(2).strip()
            metadata['semester'] = match.group(3).strip()
            return metadata

        match = re.search(r'برنامج\s+([^-]+?)\s*-\s*المستوى\s+([^-]+?)\s*-\s*الفصل\s+الدراسي\s+(.+)', header)
        if match:
            metadata['program'] = match.group(1).strip()
            metadata['level'] = match.group(2).strip()
            metadata['semester'] = match.group(3).strip()
            return metadata

        parts = [p.strip() for p in header.split('-')]
        if len(parts) >= 3:
            metadata['program'] = parts[0]
            metadata['level'] = parts[1]
            metadata['semester'] = parts[2]

        return metadata

    def process_simpler_splitter(self, texts: List[str], metadatas: List[dict],
                              chunk_size: int, overlap_size: int = 200,
                              splitter_tag: str = "\n"):

        full_text = "\n".join(texts)
        lines = full_text.split("\n")
        chunks = []
        current_chunk = ""
        current_metadata = {}

        for line in lines:
            stripped = line.strip()

            if stripped.startswith("##"):
                header_meta = self.extract_metadata_from_header(stripped)
                if header_meta:
                    current_metadata = header_meta

            if re.match(r'^\s*---\s*$', line):
                if current_chunk.strip():
                    chunks.append(Document(
                        page_content=current_chunk.strip(),
                        metadata=dict(current_metadata)
                    ))
                current_chunk = ""
                continue

            current_chunk += line + "\n"

            if len(current_chunk) >= chunk_size:
                chunks.append(Document(
                    page_content=current_chunk.strip(),
                    metadata=dict(current_metadata)
                ))
                current_chunk = current_chunk[-overlap_size:] if overlap_size > 0 else ""

        if current_chunk.strip():
            chunks.append(Document(
                page_content=current_chunk.strip(),
                metadata=dict(current_metadata)
            ))

        return chunks

    def process_table_splitter(self, texts: List[str], metadatas: List[dict]) -> List[Document]:
        
        full_text = "\n".join(texts)
        
        # Only match --- that stands alone on a line (not inside table rows)
        raw_tables = re.split(r'(?m)^\s*---\s*$', full_text)
        
        chunks = []
        for i, table_text in enumerate(raw_tables):
            cleaned = table_text.strip()
            if not cleaned:
                continue

            header_line = ""
            for line in cleaned.splitlines():
                if line.strip().startswith("##"):
                    header_line = line.strip()
                    break

            metadata = {"table_index": i}
            if header_line:
                header_meta = self.extract_metadata_from_header(header_line)
                if header_meta:
                    metadata.update(header_meta)
                metadata["table_title"] = header_line.replace("##", "").strip()

            chunks.append(Document(
                page_content=cleaned,
                metadata=metadata
            ))
        
        return chunks