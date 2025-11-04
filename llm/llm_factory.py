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
        model = os.getenv("OLLAMA_MODEL", "llama2")
        return OllamaClient(endpoint=endpoint, model=model)

    elif provider == "ollama_network":
        endpoint = os.getenv("LLM_ENDPOINT")
        if not endpoint:
            raise ValueError("LLM_ENDPOINT required for ollama_network")
        model = os.getenv("OLLAMA_MODEL", "llama2")
        return OllamaClient(endpoint=endpoint, model=model)

    elif provider == "openai":
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            raise ValueError("OPENAI_API_KEY required for openai provider")
        model = os.getenv("OPENAI_MODEL", "gpt-3.5-turbo")
        return OpenAIClient(api_key=api_key, model=model)

    else:
        raise ValueError(f"Unknown LLM provider: {provider}")
