"""
LLM factory for provider selection
"""
import os
from typing import Optional
from .llm_client import LLMClient
from .ollama_client import OllamaClient
from .openai_client import OpenAIClient


def get_llm_client() -> LLMClient:
    """
    Get LLM client based on LLM_PROVIDER environment variable

    Returns:
        LLMClient instance
    """
    provider = os.getenv("LLM_PROVIDER", "ollama_local").lower()

    if provider == "ollama_local":
        endpoint = os.getenv("LLM_ENDPOINT", "http://localhost:11434")
        model = os.getenv("OLLAMA_MODEL")
        if not model:
            raise ValueError("OLLAMA_MODEL environment variable must be set. No hardcoded defaults allowed.")
        return OllamaClient(endpoint=endpoint, model=model)

    elif provider == "ollama_network":
        endpoint = os.getenv("LLM_ENDPOINT")
        if not endpoint:
            raise ValueError("LLM_ENDPOINT required for ollama_network")
        model = os.getenv("OLLAMA_MODEL")
        if not model:
            raise ValueError("OLLAMA_MODEL environment variable must be set. No hardcoded defaults allowed.")
        enable_thinking = os.getenv("ENABLE_THINKING", "false").lower() == "true"
        return OllamaClient(endpoint=endpoint, model=model, enable_thinking=enable_thinking)

    elif provider == "openai":
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            raise ValueError("OPENAI_API_KEY required for openai provider")
        model = os.getenv("OPENAI_MODEL")
        if not model:
            raise ValueError("OPENAI_MODEL environment variable must be set")
        return OpenAIClient(api_key=api_key, model=model)

    else:
        raise ValueError(f"Unknown LLM provider: {provider}")
