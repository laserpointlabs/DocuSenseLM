"""
Ollama LLM client (local or network)
"""
import os
import httpx
from typing import List, Dict, Optional
from .llm_client import LLMClient, Chunk, Citation, Answer
from .prompts import (
    build_system_prompt, 
    build_user_prompt, 
    build_cross_document_prompt, 
    build_conversational_system_prompt,
    build_conversational_prompt,
    detect_question_type,
    is_conversational_question
)


class OllamaClient(LLMClient):
    """Ollama API client"""

    def __init__(self, endpoint: str = None, model: str = None, enable_thinking: bool = False, conversation_model: str = None):
        """
        Initialize Ollama client

        Args:
            endpoint: Ollama API endpoint (default from env)
            model: Model name to use (must be provided or set via OLLAMA_MODEL env var)
            enable_thinking: Enable thinking mode for models that support it (e.g., Granite)
            conversation_model: Optional model name for conversational responses (defaults to OLLAMA_CONVERSATION_MODEL env var, falls back to main model)
        """
        self.endpoint = endpoint or os.getenv("LLM_ENDPOINT", "http://localhost:11434")
        self.model = model or os.getenv("OLLAMA_MODEL")
        if not self.model:
            raise ValueError("OLLAMA_MODEL environment variable must be set. No hardcoded defaults allowed.")
        
        # Conversation model: use provided, env var, or fallback to main model
        self.conversation_model = conversation_model or os.getenv("OLLAMA_CONVERSATION_MODEL") or self.model
        
        # Keep-alive duration: how long to keep models loaded in memory (in seconds)
        # Default: 5 minutes (300s) - keeps models warm for faster switching
        keep_alive_str = os.getenv("OLLAMA_KEEP_ALIVE", "300")
        try:
            self.keep_alive = int(keep_alive_str)
        except ValueError:
            self.keep_alive = 300  # Default to 5 minutes
        
        # Enable thinking mode for Granite models if not explicitly set
        self.enable_thinking = enable_thinking or os.getenv("ENABLE_THINKING", "false").lower() == "true"
        if "granite" in self.model.lower() and not enable_thinking:
            # Auto-enable thinking for Granite models
            self.enable_thinking = True
        
        # Configure timeouts: 10s connect, 120s read (for generation with context)
        # Note: First request may take 30s+ to load model, then generation can take 60s+ with large context
        timeout = httpx.Timeout(10.0, read=120.0)
        self.client = httpx.AsyncClient(timeout=timeout)
        
        # Log configuration
        import logging
        logger = logging.getLogger(__name__)
        logger.info(f"OllamaClient initialized: endpoint={self.endpoint}, model={self.model}, conversation_model={self.conversation_model}, thinking={self.enable_thinking}, keep_alive={self.keep_alive}s")
        
        # Warn if using host.docker.internal when running in Docker (should use 'ollama' service name)
        if "host.docker.internal" in self.endpoint:
            logger.warning(
                f"⚠️  Using host.docker.internal endpoint. If running in Docker Compose, "
                f"consider using 'http://ollama:11434' instead for better performance and reliability."
            )
        

    async def _health_check(self) -> bool:
        """Check if Ollama endpoint is accessible"""
        import logging
        logger = logging.getLogger(__name__)
        try:
            response = await self.client.get(f"{self.endpoint}/api/tags", timeout=5.0)
            if response.status_code == 200:
                logger.info(f"✅ Ollama health check passed: {self.endpoint}")
                return True
            else:
                logger.warning(f"⚠️  Ollama health check failed: status {response.status_code}")
                return False
        except Exception as e:
            logger.error(f"❌ Ollama health check failed: {e}")
            logger.error(f"   Endpoint: {self.endpoint}")
            logger.error(f"   Make sure Ollama is running and accessible at this endpoint")
            return False

    async def generate_answer(
        self,
        query: str,
        context_chunks: List[Chunk],
        citations: List[Citation],
        use_conversational: bool = False,
        additional_info: str = ""
    ) -> Answer:
        """
        Generate answer using Ollama
        
        Args:
            query: User question
            context_chunks: Retrieved document chunks
            citations: Citation information
            use_conversational: Whether to use conversational mode (auto-detected if False)
            additional_info: Optional additional information (e.g., calculated days/months)
        """

        import logging
        logger = logging.getLogger(__name__)
        
        # Auto-detect conversational questions if not explicitly set
        if not use_conversational:
            use_conversational = is_conversational_question(query)
        
        # Select model: use conversation model for conversational questions
        model_to_use = self.conversation_model if use_conversational else self.model
        logger.info(f"Using {'conversational' if use_conversational else 'structured'} mode with model: {model_to_use}")
        

        # Build context from chunks
        # Context length comes from environment variable (no hardcoded defaults)
        context_length = os.getenv("OLLAMA_CONTEXT_LENGTH")
        if not context_length:
            raise ValueError("OLLAMA_CONTEXT_LENGTH environment variable must be set. No hardcoded defaults allowed.")
        context_length = int(context_length)
        max_tokens = int(context_length * 0.75)  # Use 75% of context window
        MAX_CONTEXT_CHARS = max_tokens * 4  # ~4 chars/token
        
        context_parts = []
        total_chars = 0
        
        for chunk in context_chunks:
            chunk_text = f"[Document {chunk.doc_id}, Clause {chunk.clause_number}, Page {chunk.page_num}]\n{chunk.text}"
            chunk_chars = len(chunk_text)
            
            # If adding this chunk would exceed limit, truncate it
            if total_chars + chunk_chars > MAX_CONTEXT_CHARS:
                remaining = MAX_CONTEXT_CHARS - total_chars
                if remaining > 100:  # Only add if we have meaningful space left
                    # Truncate the chunk text to fit
                    truncated_text = chunk.text[:remaining - 100]  # Leave room for metadata
                    chunk_text = f"[Document {chunk.doc_id}, Clause {chunk.clause_number}, Page {chunk.page_num}]\n{truncated_text}..."
                    context_parts.append(chunk_text)
                    logger.warning(f"Truncated chunk to fit context limit. Original: {chunk_chars} chars, Used: {len(chunk_text)} chars")
                break
            
            context_parts.append(chunk_text)
            total_chars += chunk_chars + 2  # +2 for "\n\n" separator
        
        context_text = "\n\n".join(context_parts)
        
        # Log token estimate
        estimated_tokens = len(context_text) // 4
        logger.info(f"Context token estimate: ~{estimated_tokens} tokens ({len(context_text)} chars)")

        # Minimal logging for performance
        logger.debug(f"Ollama request: {len(context_chunks)} chunks, {len(context_text)} chars, model={model_to_use}, conversational={use_conversational}")

        # Build prompts based on mode
        if use_conversational:
            # Use conversational prompts
            system_prompt = build_conversational_system_prompt()
            question_type = detect_question_type(query)
            if question_type == "cross_document":
                user_prompt = build_cross_document_prompt(query, context_chunks, citations)
            else:
                user_prompt = build_conversational_prompt(query, context_chunks, citations, additional_info)
        else:
            # Use structured prompts
            question_type = detect_question_type(query)
            logger.info(f"Detected question type: {question_type}")
            
            if question_type == "cross_document":
                user_prompt = build_cross_document_prompt(query, context_chunks, citations)
            else:
                user_prompt = build_user_prompt(query, context_chunks, citations)
            
            system_prompt = build_system_prompt()
        
        try:
            # Build request payload with keep_alive to keep model warm
            request_payload = {
                "model": model_to_use,
                "keep_alive": f"{self.keep_alive}s",  # Keep model loaded for faster subsequent requests
                "stream": False
            }
            
            if self.enable_thinking and "granite" in model_to_use.lower():
                # Use chat API with thinking mode
                messages = [
                    {"role": "control", "content": "thinking"},
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ]
                
                request_payload["messages"] = messages
                
                response = await self.client.post(
                    f"{self.endpoint}/api/chat",
                    json=request_payload
                )
                response.raise_for_status()
                result = response.json()
                answer_text = result.get("message", {}).get("content", "").strip()
                logger.info(f"Used chat API with thinking mode for Granite")
            else:
                # Use generate API (standard Ollama format)
                prompt = f"""{system_prompt}

{user_prompt}"""
                
                request_payload["prompt"] = prompt
                
                response = await self.client.post(
                    f"{self.endpoint}/api/generate",
                    json=request_payload
                )
                response.raise_for_status()
                result = response.json()
                answer_text = result.get("response", "").strip()

            if not answer_text:
                answer_text = "I cannot find this information in the provided documents"

            logger.debug(f"Ollama response: {len(answer_text)} chars (thinking={self.enable_thinking})")

            return Answer(
                text=answer_text,
                citations=citations
            )
        except httpx.ConnectError as e:
            error_msg = f"Cannot connect to Ollama at {self.endpoint}. Is Ollama running? Error: {e}"
            logger.error(error_msg)
            raise Exception(error_msg)
        except httpx.TimeoutException as e:
            error_msg = f"Request to Ollama timed out after 120s. Endpoint: {self.endpoint}, Model: {model_to_use}. The model may need to be loaded first (takes ~30s), or the context may be too large."
            logger.error(error_msg)
            raise Exception(error_msg)
        except httpx.HTTPStatusError as e:
            error_msg = f"Ollama API returned error {e.response.status_code}: {e.response.text}"
            logger.error(error_msg)
            raise Exception(error_msg)
        except Exception as e:
            error_msg = f"Ollama API error: {e}"
            logger.error(error_msg)
            raise Exception(error_msg)

    async def generate_question_suggestions(
        self,
        document_text: str,
        category: Optional[str] = None
    ) -> List[str]:
        """Generate question suggestions using Ollama"""

        category_hint = f"Focus on {category}." if category else ""

        prompt = f"""You are analyzing an NDA document. Generate 5-10 relevant questions that would help understand the key terms and obligations in this document.

{category_hint}

Document excerpt:
{document_text[:2000]}...

Generate specific, answerable questions about:
- Confidentiality scope and definitions
- Obligations and restrictions
- Exceptions to confidentiality
- Term and survival periods
- Governing law and jurisdiction
- Mutual vs unilateral obligations

Format as a numbered list of questions."""

        try:
            request_payload = {
                "model": self.model,
                "prompt": prompt,
                "keep_alive": f"{self.keep_alive}s",
                "stream": False
            }
            
            response = await self.client.post(
                f"{self.endpoint}/api/generate",
                json=request_payload
            )
            response.raise_for_status()
            result = response.json()

            text = result.get("response", "")
            # Parse numbered list
            questions = []
            for line in text.split('\n'):
                line = line.strip()
                if line and (line[0].isdigit() or line.startswith('-')):
                    # Remove numbering/bullets
                    question = line.split('.', 1)[-1].strip()
                    if question.startswith('-'):
                        question = question[1:].strip()
                    if question and len(question) > 10:
                        questions.append(question)

            return questions[:10]  # Return up to 10 questions
        except httpx.ConnectError as e:
            raise Exception(f"Cannot connect to Ollama at {self.endpoint}. Is Ollama running? Error: {e}")
        except httpx.TimeoutException as e:
            raise Exception(f"Request to Ollama timed out. Endpoint: {self.endpoint}, Model: {self.model}")
        except Exception as e:
            raise Exception(f"Ollama API error: {e}")

    async def close(self):
        """Close HTTP client"""
        await self.client.aclose()
