"""
Lightweight service registry to support dependency injection and test overrides.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Dict, Optional


class ServiceNotRegisteredError(RuntimeError):
    """Raised when attempting to access an unregistered service."""


@dataclass
class _ServiceEntry:
    factory: Callable[[], Any]
    instance: Optional[Any] = None


_services: Dict[str, _ServiceEntry] = {}


def register_service(name: str, factory: Callable[[], Any]) -> None:
    """
    Register a factory for a service.

    The factory will be invoked lazily the first time the service is requested.
    """
    _services[name] = _ServiceEntry(factory=factory, instance=None)


def override_service(name: str, instance: Any) -> None:
    """
    Override an existing service with a concrete instance (useful for tests).
    """
    _services[name] = _ServiceEntry(factory=lambda: instance, instance=instance)


def reset_service(name: str) -> None:
    """
    Reset the cached instance for a service while keeping its factory.
    """
    if name in _services:
        _services[name].instance = None


def get_service(name: str) -> Any:
    """
    Retrieve a service instance, creating it from the registered factory if needed.
    """
    entry = _services.get(name)
    if entry is None:
        raise ServiceNotRegisteredError(f"Service '{name}' has not been registered.")

    if entry.instance is None:
        entry.instance = entry.factory()
    return entry.instance


# Convenience wrappers for known services -----------------------------------

STORAGE_SERVICE = "storage"
EMBEDDER_SERVICE = "embedder"
SEARCH_SERVICE = "search_backend"
LLM_SERVICE = "llm_client"
BM25_INDEXER = "bm25_indexer"
VECTOR_INDEXER = "vector_indexer"
EMAIL_SERVICE = "email_service"


def register_storage_service(factory: Callable[[], Any]) -> None:
    register_service(STORAGE_SERVICE, factory)


def get_storage_service() -> Any:
    return get_service(STORAGE_SERVICE)


def register_email_service(factory: Callable[[], Any]) -> None:
    register_service(EMAIL_SERVICE, factory)


def get_email_service() -> Any:
    return get_service(EMAIL_SERVICE)


def override_storage_service(instance: Any) -> None:
    override_service(STORAGE_SERVICE, instance)


def reset_storage_service() -> None:
    reset_service(STORAGE_SERVICE)


def register_embedder_service(factory: Callable[[], Any]) -> None:
    register_service(EMBEDDER_SERVICE, factory)


def get_embedder_service() -> Any:
    return get_service(EMBEDDER_SERVICE)


def override_embedder_service(instance: Any) -> None:
    override_service(EMBEDDER_SERVICE, instance)


def reset_embedder_service() -> None:
    reset_service(EMBEDDER_SERVICE)


def register_search_service(factory: Callable[[], Any]) -> None:
    register_service(SEARCH_SERVICE, factory)


def get_search_service() -> Any:
    return get_service(SEARCH_SERVICE)


def override_search_service(instance: Any) -> None:
    override_service(SEARCH_SERVICE, instance)


def reset_search_service() -> None:
    reset_service(SEARCH_SERVICE)


def register_llm_service(factory: Callable[[], Any]) -> None:
    register_service(LLM_SERVICE, factory)


def get_llm_service() -> Any:
    return get_service(LLM_SERVICE)


def override_llm_service(instance: Any) -> None:
    override_service(LLM_SERVICE, instance)


def reset_llm_service() -> None:
    reset_service(LLM_SERVICE)


def register_bm25_indexer(factory: Callable[[], Any]) -> None:
    register_service(BM25_INDEXER, factory)


def get_bm25_indexer() -> Any:
    return get_service(BM25_INDEXER)


def override_bm25_indexer(instance: Any) -> None:
    override_service(BM25_INDEXER, instance)


def reset_bm25_indexer() -> None:
    reset_service(BM25_INDEXER)


def register_vector_indexer(factory: Callable[[], Any]) -> None:
    register_service(VECTOR_INDEXER, factory)


def get_vector_indexer() -> Any:
    return get_service(VECTOR_INDEXER)


def override_vector_indexer(instance: Any) -> None:
    override_service(VECTOR_INDEXER, instance)


def reset_vector_indexer() -> None:
    reset_service(VECTOR_INDEXER)
