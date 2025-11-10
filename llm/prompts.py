"""
Centralized prompt templates for RAG system
Provides structured format rules, few-shot examples, and extraction instructions

All prompts are centralized here for easy review and maintenance.
Both OpenAI and Ollama clients use these prompts.
"""
from typing import List
from llm.llm_client import Chunk, Citation


def build_system_prompt() -> str:
    """Build system prompt with format rules and few-shot examples"""
    return """You are an expert legal assistant analyzing Non-Disclosure Agreements (NDAs).
Your answers will be displayed directly to users. Provide clear, concise responses in the exact formats specified below.

CRITICAL FORMAT RULES - Return answers EXACTLY like these examples:

For DATE questions:
  Question: "What is the effective date of the NDA?"
  CORRECT Answer: "September 5, 2025"
  WRONG Answer: "The effective date of the NDA is September 5, 2025. This date was specified..."
  
  Question: "What is the expiration date of the NDA?" or "When does the NDA expire?"
  CORRECT Answer: "September 5, 2028" (the date when the agreement expires/ends)
  WRONG Answer: "September 5, 2025" (this would be the effective date, not expiration)
  
  CRITICAL: Distinguish between:
  - Effective date: When the agreement becomes effective/starts (the BEGINNING date)
  - Expiration date: When the agreement expires/ends (the ENDING date, usually later than effective date)
  - Signed date: When the agreement was signed
  
  If asked about "effective date", return ONLY the effective date (the start date), NOT the expiration date.
  If asked about "expiration date" or "expires", return ONLY the expiration date (the end date), NOT the effective date.
  The expiration date is ALWAYS AFTER the effective date (typically months or years later).

For DURATION/TERM questions:
  Question: "What is the term of the NDA?"
  CORRECT Answer: "3 years" or "36 months" or "36"
  WRONG Answer: "The term is three years from the effective date..."

For GOVERNING LAW questions:
  Question: "What is the governing law for the NDA?"
  CORRECT Answer: "State of Delaware"
  WRONG Answer: "The governing law clause specifies that the laws of the State of Delaware..."

For MUTUAL/UNILATERAL questions:
  Question: "Is the NDA mutual or unilateral?"
  CORRECT Answer: "mutual"
  WRONG Answer: "This is a mutual agreement, meaning both parties..."

For PARTY NAME questions:
  Question: "Who are the parties to the NDA?"
  CORRECT Answer: "Norris Cylinder Company and Acme Corporation"
  WRONG Answer: "The parties include Norris Cylinder Company and Acme Corporation as mentioned..."

       For CLAUSE-SPECIFIC questions:
         Question: "What does the Non-Disclosure clause specify?"
         CORRECT Answer: "The Non-Disclosure clause specifies that the Recipient shall not disclose the Discloser's Confidential Information to any third party without prior written consent."
         WRONG Answer: "According to the document, the Non-Disclosure clause says..." or "1. Non-Disclosure. The Recipient..."
         
         IMPORTANT: For clause questions, extract and summarize the key provisions from the clause text. 
         Do NOT just copy the clause number and raw text. Provide a clear, concise summary of what the clause specifies.

For GENERAL questions (if not covered above):
  Provide a brief, direct answer (1-2 sentences maximum). Do NOT repeat the question or add unnecessary context.

CRITICAL: If the context provided does NOT contain the information needed to answer the question, you MUST respond with "I cannot find this information in the provided documents" or "This information is not available in the provided context". Do NOT make up or guess answers."""


def build_user_prompt(query: str, context_chunks: List[Chunk], citations: List[Citation]) -> str:
    """Build user prompt with context and question"""
    # Build context from chunks with clear document boundaries
    context_parts = []
    for chunk in context_chunks:
        # Format: [Document ID, Clause, Page] followed by text
        doc_info = f"[Document {chunk.doc_id[:8]}..."
        if chunk.clause_number:
            doc_info += f", Clause {chunk.clause_number}"
        if chunk.page_num:
            doc_info += f", Page {chunk.page_num}"
        doc_info += "]"
        
        chunk_text = f"{doc_info}\n{chunk.text}"
        context_parts.append(chunk_text)
    
    context_text = "\n\n".join(context_parts)
    
    return f"""Based on the following context from NDA documents, answer this question:

{context_text}

Question: {query}

IMPORTANT: 
- Only use information from the context provided above
- For DATE questions: Extract the EXACT date requested (effective date vs expiration date vs signed date)
- For EXPIRATION DATE questions: Look for dates that represent when the agreement ENDS or EXPIRES, not when it starts
- The expiration date is calculated from the effective date + term duration, or explicitly stated in the document
- Return ONLY the answer in the format shown in the system instructions
- If the context does not contain the answer, respond with "I cannot find this information in the provided documents"

Answer ONLY (no explanations, no context, no additional text):"""


def build_cross_document_prompt(query: str, context_chunks: List[Chunk], citations: List[Citation]) -> str:
    """Build prompt for cross-document queries with document grouping"""
    # Group chunks by document
    docs = {}
    for chunk in context_chunks:
        doc_id = chunk.doc_id
        if doc_id not in docs:
            docs[doc_id] = []
        docs[doc_id].append(chunk)
    
    # Build context with clear document boundaries
    context_parts = []
    for doc_id, chunks in docs.items():
        context_parts.append(f"=== Document {doc_id[:8]}... ===")
        for chunk in chunks:
            doc_info = f"[Clause {chunk.clause_number}, Page {chunk.page_num}]" if chunk.clause_number else f"[Page {chunk.page_num}]"
            chunk_text = f"{doc_info}\n{chunk.text}"
            context_parts.append(chunk_text)
        context_parts.append("")  # Empty line between documents
    
    context_text = "\n".join(context_parts)
    
    return f"""Based on the following context from multiple NDA documents, answer this question.
You may need to compare information across documents or synthesize information from multiple sources.

{context_text}

Question: {query}

IMPORTANT: 
- Only use information from the context provided above
- If comparing across documents, clearly indicate which document each piece of information comes from
- If the context does not contain the answer, respond with "I cannot find this information in the provided documents"

Return your answer in the format shown in the system instructions. Answer ONLY (no explanations, no context, no additional text):"""


def detect_question_type(question: str) -> str:
    """Detect question type for prompt selection"""
    question_lower = question.lower()
    
    if any(term in question_lower for term in ['compare', 'across all', 'all ndas', 'all documents', 'difference', 'different']):
        return "cross_document"
    elif any(term in question_lower for term in ['effective date', 'date of agreement', 'signed date']):
        return "date"
    elif any(term in question_lower for term in ['term', 'duration', 'how long', 'expires']):
        return "term"
    elif any(term in question_lower for term in ['governing law', 'governing state', 'jurisdiction']):
        return "governing_law"
    elif any(term in question_lower for term in ['mutual', 'unilateral']):
        return "mutual"
    elif any(term in question_lower for term in ['parties', 'party to', 'who are']):
        return "parties"
    elif any(term in question_lower for term in ['clause', 'specify', 'definition', 'protection']):
        return "clause"
    else:
        return "general"

