#!/usr/bin/env python3
"""
Preload Ollama models at startup to avoid user wait time.
This script loads models with keep_alive so they stay warm.
"""
import os
import sys
import time
import httpx
from typing import Optional

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def preload_model(endpoint: str, model: str, keep_alive: str = "24h") -> bool:
    """
    Preload a model by sending a small request with keep_alive.
    
    Args:
        endpoint: Ollama API endpoint
        model: Model name to preload
        keep_alive: How long to keep model loaded (default: 24h)
        
    Returns:
        True if successful, False otherwise
    """
    try:
        client = httpx.Client(timeout=300.0)  # 5 minute timeout for large models
        
        print(f"🔄 Preloading model: {model}...")
        
        # Send a small prompt to load the model
        # This will load it into memory and keep it warm
        response = client.post(
            f"{endpoint}/api/generate",
            json={
                "model": model,
                "prompt": "test",  # Minimal prompt just to load the model
                "keep_alive": keep_alive,
                "stream": False
            }
        )
        
        if response.status_code == 200:
            print(f"✅ Model {model} preloaded successfully")
            return True
        else:
            print(f"⚠️  Failed to preload {model}: HTTP {response.status_code}")
            print(f"   Response: {response.text[:200]}")
            return False
            
    except Exception as e:
        print(f"❌ Error preloading {model}: {e}")
        return False
    finally:
        client.close()


def check_ollama_health(endpoint: str, max_retries: int = 30, retry_delay: int = 2) -> bool:
    """
    Check if Ollama is ready, with retries.
    
    Args:
        endpoint: Ollama API endpoint
        max_retries: Maximum number of retries
        retry_delay: Delay between retries in seconds
        
    Returns:
        True if Ollama is ready, False otherwise
    """
    for attempt in range(max_retries):
        try:
            client = httpx.Client(timeout=5.0)
            response = client.get(f"{endpoint}/api/version")
            client.close()
            
            if response.status_code == 200:
                print(f"✅ Ollama is ready at {endpoint}")
                return True
        except Exception as e:
            if attempt < max_retries - 1:
                print(f"⏳ Waiting for Ollama... (attempt {attempt + 1}/{max_retries})")
                time.sleep(retry_delay)
            else:
                print(f"❌ Ollama not ready after {max_retries} attempts: {e}")
                return False
    
    return False


def main():
    """Main preload function"""
    print("="*80)
    print("🚀 Ollama Model Preloader")
    print("="*80)
    
    # Get configuration from environment
    endpoint = os.getenv("LLM_ENDPOINT", "http://localhost:11434")
    main_model = os.getenv("OLLAMA_MODEL")
    conversation_model = os.getenv("OLLAMA_CONVERSATION_MODEL")
    keep_alive = os.getenv("OLLAMA_KEEP_ALIVE", "24h")  # Keep models loaded for 24 hours
    
    if not main_model:
        print("⚠️  OLLAMA_MODEL not set, skipping preload")
        return
    
    # Wait for Ollama to be ready
    if not check_ollama_health(endpoint):
        print("❌ Ollama is not available, cannot preload models")
        sys.exit(1)
    
    # Preload main model
    success = preload_model(endpoint, main_model, keep_alive)
    
    # Preload conversation model if different from main model
    if conversation_model and conversation_model != main_model:
        print()  # Blank line
        success = preload_model(endpoint, conversation_model, keep_alive) and success
    
    if success:
        print()
        print("="*80)
        print("✅ Model preloading complete!")
        print("="*80)
        print(f"📌 Models will stay loaded for: {keep_alive}")
        print("💡 Users won't have to wait for model loading")
    else:
        print()
        print("⚠️  Some models failed to preload")
        sys.exit(1)


if __name__ == "__main__":
    main()

