# === TASK:WP-008:START ===
from dataclasses import dataclass, field
from typing import List, Optional

@dataclass
class ChunkRecord:
    chunk_id: str = ""
    external_chunk_id: str = ""
    content: str = ""
    embedding_text: str = ""
    domain: str = ""
    sub_topic: str = ""
    source_id: str = ""
    source_kind: str = "web"
    title: str = ""
    display_name: str = ""
    source_url: Optional[str] = None
    ingestion_path: str = ""
    publisher: str = "Bệnh viện Tim Hà Nội"
    topic: str = ""
    section_path: str = ""
    source_section: str = ""
    source_page: str = ""
    version: str = "1.0"
    is_active: bool = True
    approval_status: str = "approved"
    effective_date: Optional[str] = None
    crawled_at: Optional[str] = None
    source_content_hash: str = ""
    content_hash: str = ""
    source_path: str = ""
    persistence_uuid: str = ""
    
    # Metadata fields
    chunker_version: str = "1.0"
    tokenizer: str = "cl100k_base"
    token_count: int = 0
    split_reason: str = "none"
    quality_flags: List[str] = field(default_factory=list)
    extraction_incomplete: bool = False
    answerable: bool = True
    tags: List[str] = field(default_factory=list)
    is_mock: bool = False
    embedding_provider: str = "jina"
    embedding_model: str = "jina-embeddings-v5-text-small"
    embedding_dimensions: Optional[int] = 1024
    embedding_identity: str = ""
    corpus_release_id: str = ""

    def __init__(self, **kwargs):
        self.tags = []
        self.quality_flags = []
        for k, v in kwargs.items():
            setattr(self, k, v)
        if not self.chunk_id and self.external_chunk_id:
            self.chunk_id = self.external_chunk_id
        if not self.source_path and self.ingestion_path:
            self.source_path = self.ingestion_path


@dataclass
class SourceRecord:
    source_id: str = ""
    source_kind: str = "web"
    title: str = ""
    display_name: str = ""
    source_url: Optional[str] = None
    ingestion_path: str = ""
    source_type: str = ""
    path: Optional[str] = None
    publisher: str = "Bệnh viện Tim Hà Nội"
    topic: str = ""
    domain_code: str = ""
    version: str = "1.0"
    approval_status: str = "approved"
    effective_date: Optional[str] = None
    crawled_at: Optional[str] = None
    source_content_hash: str = ""
    extraction_incomplete: bool = False
    quality_flags: List[str] = field(default_factory=list)
    is_mock: bool = False
    ingestible: bool = True
    is_active: bool = True

    def __init__(self, **kwargs):
        self.quality_flags = []
        for k, v in kwargs.items():
            setattr(self, k, v)
        if not self.ingestion_path and self.path:
            self.ingestion_path = self.path



@dataclass
class ImportPlan:
    to_insert: List[ChunkRecord] = field(default_factory=list)
    to_update: List[ChunkRecord] = field(default_factory=list)
    to_skip: List[ChunkRecord] = field(default_factory=list)
    to_retire: List[str] = field(default_factory=list)

    def __init__(self, **kwargs):
        self.to_insert = []
        self.to_update = []
        self.to_skip = []
        self.to_retire = []
        for k, v in kwargs.items():
            setattr(self, k, v)


@dataclass
class IngestionResult:
    total_chunks: int = 0
    answerable_chunks: int = 0
    mock_chunks: int = 0
    approved_chunks: int = 0
    errors: List[str] = field(default_factory=list)
    chunk_records: List[ChunkRecord] = field(default_factory=list)
    inserted: int = 0
    updated: int = 0
    retired: int = 0
    vector_dim: Optional[int] = None

    def __init__(self, **kwargs):
        self.errors = []
        self.chunk_records = []
        self.inserted = 0
        self.updated = 0
        self.retired = 0
        self.vector_dim = None
        for k, v in kwargs.items():
            setattr(self, k, v)

    @property
    def has_errors(self) -> bool:
        return len(self.errors) > 0
# === TASK:WP-008:END ===
