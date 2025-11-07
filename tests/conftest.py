import os

# Ensure the application uses an in-memory SQLite database during tests
os.environ.setdefault("POSTGRES_URL", "sqlite:///:memory:")
os.environ.setdefault("SERVICE_PROFILE", "test")


import pytest
from sqlalchemy import create_engine, String
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from sqlalchemy.types import TypeDecorator
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
import uuid

from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

STUBS_DIR = Path(__file__).resolve().parent / "stubs"
if str(STUBS_DIR) not in sys.path:
    sys.path.insert(0, str(STUBS_DIR))

from api import db as db_module
from api.db.schema import Base


class SQLiteUUID(TypeDecorator):
    """UUID type that works with SQLite by storing as string."""
    impl = String
    cache_ok = True

    def load_dialect_impl(self, dialect):
        if dialect.name == "postgresql":
            return dialect.type_descriptor(PG_UUID(as_uuid=True))
        else:
            return dialect.type_descriptor(String(36))

    def process_bind_param(self, value, dialect):
        if value is None:
            return value
        elif dialect.name == "postgresql":
            return value
        else:
            if isinstance(value, uuid.UUID):
                return str(value)
            return value

    def process_result_value(self, value, dialect):
        if value is None:
            return value
        elif dialect.name == "postgresql":
            return value
        else:
            if isinstance(value, str):
                return uuid.UUID(value)
            return value
from api.services.bootstrap import configure_services_from_env
from api.services.service_registry import (
    override_storage_service,
    reset_storage_service,
    override_embedder_service,
    reset_embedder_service,
    override_search_service,
    reset_search_service,
    override_llm_service,
    reset_llm_service,
    override_bm25_indexer,
    reset_bm25_indexer,
    override_vector_indexer,
    reset_vector_indexer,
)
from api.services.fakes import (
    InMemoryStorageService,
    DeterministicEmbedder,
    InMemoryBM25Backend,
    InMemoryVectorBackend,
    InMemoryBM25Indexer,
    InMemoryVectorIndexer,
    EchoLLMClient,
)
from api.services.search_service import SearchService
from api.services.rerank import get_reranker

configure_services_from_env()


@pytest.fixture(autouse=True)
def configure_sqlite_db():
    """Configure the ORM to use an in-memory SQLite database for each test."""
    # Patch UUID columns to use SQLite-compatible type before creating tables
    for table in Base.metadata.tables.values():
        for column in table.columns:
            if isinstance(column.type, PG_UUID):
                # Replace with SQLite-compatible UUID type
                column.type = SQLiteUUID()
    
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    testing_session_local = sessionmaker(autocommit=False, autoflush=False, bind=engine)

    db_module.engine = engine
    db_module.SessionLocal = testing_session_local

    try:
        Base.metadata.drop_all(bind=engine)
        Base.metadata.create_all(bind=engine)
    except Exception:
        # If creation fails, restore types and re-raise
        for table in Base.metadata.tables.values():
            for column in table.columns:
                if isinstance(column.type, SQLiteUUID):
                    column.type = PG_UUID(as_uuid=True)
        raise

    yield

    engine.dispose()
    
    # Restore original UUID types
    for table in Base.metadata.tables.values():
        for column in table.columns:
            if isinstance(column.type, SQLiteUUID):
                column.type = PG_UUID(as_uuid=True)


@pytest.fixture(autouse=True)
def override_storage():
    storage = InMemoryStorageService()
    override_storage_service(storage)
    try:
        yield
    finally:
        reset_storage_service()


@pytest.fixture
def fake_service_registry():
    embedder = DeterministicEmbedder()
    bm25_backend = InMemoryBM25Backend()
    vector_backend = InMemoryVectorBackend()
    reranker = get_reranker(os.getenv("RERANK_STRATEGY", "rrf"))
    search = SearchService(
        bm25_backend=bm25_backend,
        vector_backend=vector_backend,
        embedder_provider=lambda: embedder,
        reranker=reranker,
    )
    llm = EchoLLMClient()
    bm25_indexer = InMemoryBM25Indexer(bm25_backend)
    vector_indexer = InMemoryVectorIndexer(vector_backend)

    override_embedder_service(embedder)
    override_search_service(search)
    override_llm_service(llm)
    override_bm25_indexer(bm25_indexer)
    override_vector_indexer(vector_indexer)

    try:
        yield {
            "embedder": embedder,
            "bm25": bm25_backend,
            "vector": vector_backend,
            "search": search,
            "llm": llm,
            "bm25_indexer": bm25_indexer,
            "vector_indexer": vector_indexer,
        }
    finally:
        reset_vector_indexer()
        reset_bm25_indexer()
        reset_llm_service()
        reset_search_service()
        reset_embedder_service()
