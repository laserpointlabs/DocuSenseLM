"""
Answer service for LLM-generated answers with citations
"""
from typing import List, Dict, Optional
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from llm.llm_factory import get_llm_client
from llm.llm_client import Chunk, Citation, Answer
from api.services.search_service import get_search_service_instance
from api.services.metadata_service import metadata_service
from api.services.query_service import query_service
from api.services.answer_evaluator import answer_evaluator
from api.services.document_finder import document_finder
from llm.prompts import is_conversational_question


class AnswerService:
    """Service for generating answers with citations"""

    def __init__(self):
        self.llm_client = None  # Lazy load

    @property
    def search(self):
        # Resolve via service registry each time to respect overrides
        return get_search_service_instance()

    async def generate_answer(
        self,
        question: str,
        filters: Optional[Dict] = None,
        max_context_chunks: int = 30
    ) -> Answer:
        """
        Generate answer using metadata-first approach for structured questions,
        then falling back to hybrid search + LLM for complex questions

        Args:
            question: User question
            filters: Optional filters (may include document_id)
            max_context_chunks: Maximum chunks to use as context

        Returns:
            Answer with citations
        """
        import logging
        logger = logging.getLogger(__name__)
        
        logger.info(f"Question: {question}, max_context_chunks: {max_context_chunks}, filters: {filters}")
        
        # Phase 4: Query Understanding and Transformation
        query_info = query_service.understand_query(question)
        logger.info(f"Query understanding: type={query_info['question_type']}, metadata={query_info['metadata']}")
        logger.info(f"Original: {query_info['original_query']}")
        logger.info(f"Transformed: {query_info['transformed_query']}")
        
        # Use transformed query for better retrieval
        retrieval_query = query_info['transformed_query']
        
        # Phase 5: Date Range Query Detection
        date_range = query_info['metadata'].get('date_range')
        if date_range and query_info['question_type'] == 'date_range':
            logger.info(f"Detected date range query: {date_range}")
            # Add date range to filters
            if filters is None:
                filters = {}
            filters['date_range'] = date_range
        
        # Phase 6: Cross-Document Detection
        is_cross_document = query_info['metadata'].get('is_cross_document', False)
        if is_cross_document:
            logger.info("Detected cross-document query, using cross-document synthesis")
            return await self._handle_cross_document_query(question, filters, max_context_chunks, query_info, logger)
        
        # Phase 1: Metadata-First Retrieval for Structured Fields
        # Check if this is a structured question that can be answered from metadata
        structured_answer = None
        
        # Detect if this is a conversational question early (before metadata lookup)
        # Conversational questions need LLM processing even if metadata is available
        is_conversational = is_conversational_question(question)
        
        # Try to find document_id if not provided but company name is in query
        # IMPORTANT: Always try to find document by company name, not just for structured questions
        # This enables flexible queries like "What date does the Faunc NDA expire?"
        document_id = None
        if filters and filters.get('document_id'):
            document_id = filters.get('document_id')
        else:
            # Try to find document by company name from query (for ALL queries, not just structured)
            found_doc_id = document_finder.find_best_document_match(question, use_fuzzy=True)
            if found_doc_id:
                document_id = found_doc_id
                logger.info(f"✅ Found document by company name: {document_id[:8]}...")
                # Update filters for downstream use
                if filters is None:
                    filters = {}
                filters['document_id'] = document_id
                logger.info(f"✅ Added document_id filter: {filters.get('document_id')[:8]}...")
            else:
                logger.warning(f"⚠️  Could not find document by company name from query: {question}")
        
        # If we have a document_id and it's a structured question, try metadata first
        # BUT skip metadata for conversational questions (they need LLM processing)
        if document_id and query_info['metadata'].get('is_structured') and not is_conversational:
            structured_answer = self._try_metadata_answer(question, document_id, logger)
            if structured_answer:
                logger.info(f"✅ Answered from metadata: {structured_answer.text[:100]}")
                # Set high confidence for metadata answers
                structured_answer.confidence = 0.95
                structured_answer.evaluation_reasoning = "Answer retrieved from structured metadata"
                return structured_answer
            else:
                logger.info("Metadata answer not available, falling back to chunk retrieval")
        
        # Phase 2: Fall back to hybrid search + LLM for complex questions
        # Determine strategy from environment variable
        rag_strategy = os.getenv("RAG_STRATEGY", "single_query").lower()
        logger.info(f"Using {rag_strategy} strategy for chunk retrieval")
        
        # Run search based on strategy (use transformed query for better retrieval)
        if rag_strategy == "two_query":
            search_results = self._two_query_search(retrieval_query, filters, max_context_chunks, logger)
        else:
            # Default: single_query
            search_results = self._single_query_search(retrieval_query, filters, max_context_chunks, logger)
        
        logger.info(f"Search returned {len(search_results)} results")

        # 2. For clause questions, boost chunks with matching clause titles
        clause_name = query_info['metadata'].get('clause_name')
        if clause_name and query_info['question_type'] == 'clause':
            logger.info(f"Clause question detected, clause_name: {clause_name}")
            clause_name_lower = clause_name.lower()
            for result in search_results:
                result_clause_title = result.get('clause_title', '').lower() if result.get('clause_title') else ''
                if result_clause_title:
                    # Boost score if clause title matches
                    if clause_name_lower in result_clause_title or result_clause_title in clause_name_lower:
                        result['score'] = result.get('score', 0) * 1.5  # 50% boost
                        logger.info(f"Boosted chunk with matching clause title: {result.get('clause_title')}")
                    elif any(word in result_clause_title for word in clause_name_lower.split() if len(word) > 3):
                        result['score'] = result.get('score', 0) * 1.2  # 20% boost
        
        # 3. Deduplicate by doc_id + page_num + clause_number, then take top chunks
        seen_chunks = {}
        for result in search_results:
            key = (result.get('doc_id'), result.get('page_num'), result.get('clause_number'))
            # Keep the highest scoring result for each unique citation
            if key not in seen_chunks or result.get('score', 0) > seen_chunks[key].get('score', 0):
                seen_chunks[key] = result

        # Convert back to list and sort
        deduplicated_results = list(seen_chunks.values())
        
        # Sort: prioritize chunks with matching clause titles, then clauses over metadata, then by score
        if clause_name:
            clause_name_lower = clause_name.lower()
            deduplicated_results.sort(
                key=lambda x: (
                    (x.get('clause_title') or '').lower() == clause_name_lower,  # Exact match first
                    clause_name_lower in ((x.get('clause_title') or '').lower()),  # Partial match
                    x.get('clause_number') is not None,  # Clauses over metadata  
                    x.get('score', 0)  # Then by score
                ),
                reverse=True
            )
        else:
            # Sort: prioritize clauses over metadata, then by score
            deduplicated_results.sort(
                key=lambda x: (
                    x.get('clause_number') is not None,  # Clauses over metadata  
                    x.get('score', 0)  # Then by score
                ),
                reverse=True
            )
        
        # Phase 6: Chunk Quality Assessment
        # Score chunks for relevance, completeness, and answer presence
        scored_chunks = self._assess_chunk_quality(deduplicated_results, question, logger)
        
        # Filter low-quality chunks and take top chunks
        quality_threshold = float(os.getenv("CHUNK_QUALITY_THRESHOLD", "0.3"))
        high_quality_chunks = [c for c in scored_chunks if c.get('quality_score', 0) >= quality_threshold]
        
        if high_quality_chunks:
            top_chunks = high_quality_chunks[:max_context_chunks]
            logger.info(f"After quality assessment: {len(top_chunks)} high-quality chunks (threshold: {quality_threshold})")
        else:
            # Fallback: use top chunks even if below threshold
            top_chunks = scored_chunks[:max_context_chunks]
            logger.warning(f"No chunks above quality threshold, using top {len(top_chunks)} chunks anyway")

        logger.info(f"After deduplication and quality assessment: {len(top_chunks)} top chunks")
        if top_chunks:
            logger.info(f"Top chunk details: doc_id={top_chunks[0].get('doc_id')}, page={top_chunks[0].get('page_num')}, clause={top_chunks[0].get('clause_number')}, has_text={bool(top_chunks[0].get('text'))}, text_length={len(top_chunks[0].get('text', ''))}")

        # 3. Convert to Chunk objects
        context_chunks = self.search.get_chunks_for_answer(top_chunks)

        # Log context chunks for debugging
        import logging
        logger = logging.getLogger(__name__)
        logger.info(f"=== Answer Service Context Building ===")
        logger.info(f"Question: {question}")
        logger.info(f"Number of top_chunks: {len(top_chunks)}")
        logger.info(f"Number of context_chunks: {len(context_chunks)}")
        if top_chunks:
            logger.info(f"First top_chunk: doc_id={top_chunks[0].get('doc_id')}, text_length={len(top_chunks[0].get('text', ''))}")
        if context_chunks:
            logger.info(f"First context_chunk: doc_id={context_chunks[0].doc_id}, clause={context_chunks[0].clause_number}, page={context_chunks[0].page_num}, text_length={len(context_chunks[0].text)}")

        # 4. Build citations - only from chunks actually sent to LLM
        citations = []
        # Map context_chunks back to original results for citation metadata
        chunk_to_result = {}
        for result in top_chunks:
            key = (result.get('doc_id'), result.get('page_num'), result.get('clause_number'))
            chunk_to_result[key] = result
        
        # Build citations only from context_chunks that were actually used
        # Deduplicate: only one citation per (doc_id, clause_number, page_num) combination
        seen_citation_keys = set()
        for chunk in context_chunks:
            key = (chunk.doc_id, chunk.page_num, chunk.clause_number)
            result = chunk_to_result.get(key)
            if result:
                # Create citation key for deduplication
                citation_key = (chunk.doc_id, chunk.clause_number, chunk.page_num)
                if citation_key not in seen_citation_keys:
                    seen_citation_keys.add(citation_key)
                citation = Citation(
                    doc_id=chunk.doc_id or '',
                    clause_number=chunk.clause_number,
                    page_num=chunk.page_num if chunk.page_num is not None else 0,
                    span_start=chunk.span_start if chunk.span_start is not None else 0,
                    span_end=chunk.span_end if chunk.span_end is not None else 0,
                    source_uri=chunk.source_uri or '',
                    excerpt=chunk.text  # Use chunk text (already has full text)
                )
                citations.append(citation)

        logger.info(f"Built {len(citations)} citations from {len(top_chunks)} top chunks")
        for i, cit in enumerate(citations[:5]):
            logger.info(f"Citation {i+1}: doc_id={cit.doc_id[:8]}..., clause={cit.clause_number}, page={cit.page_num}, excerpt_length={len(cit.excerpt)}")

        # 5. Detect conversational questions and prepare additional info
        # Use original question for LLM (not transformed query which was only for retrieval)
        original_question = query_info.get('original_query', question)
        
        # Use the conversational detection from earlier (already computed)
        # Re-check to be sure we're using the original question
        is_conversational = is_conversational_question(original_question)
        additional_info = ""
        
        # For conversational questions asking about days/months, calculate and provide the info
        if is_conversational:
            question_lower = original_question.lower()
            
            # Check for "what NDAs expire next/this month" type questions
            if any(term in question_lower for term in ['what ndas', 'what agreements', 'which ndas', 'which agreements']) and \
               any(term in question_lower for term in ['next month', 'this month', 'next year', 'this year', 'expire next', 'expire in']):
                from datetime import datetime
                from dateutil.relativedelta import relativedelta
                import re
                
                today = datetime.now()
                target_month = None
                target_year = None
                
                # Try to extract month/year from question (e.g., "expire in June 2028")
                month_names = {
                    'january': 1, 'february': 2, 'march': 3, 'april': 4, 'may': 5, 'june': 6,
                    'july': 7, 'august': 8, 'september': 9, 'october': 10, 'november': 11, 'december': 12,
                    'jan': 1, 'feb': 2, 'mar': 3, 'apr': 4, 'may': 5, 'jun': 6,
                    'jul': 7, 'aug': 8, 'sep': 9, 'sept': 9, 'oct': 10, 'nov': 11, 'dec': 12
                }
                
                # Pattern: "in [Month] [Year]" or "in [Month]" (assumes current or next year)
                month_year_pattern = r'in\s+(\w+)\s+(\d{4})'
                month_only_pattern = r'in\s+(\w+)'
                
                month_year_match = re.search(month_year_pattern, question_lower)
                if month_year_match:
                    month_name = month_year_match.group(1).lower()
                    year_str = month_year_match.group(2)
                    if month_name in month_names:
                        target_month = month_names[month_name]
                        target_year = int(year_str)
                else:
                    # Try month only pattern
                    month_match = re.search(month_only_pattern, question_lower)
                    if month_match:
                        month_name = month_match.group(1).lower()
                        if month_name in month_names:
                            target_month = month_names[month_name]
                            # If year not specified, use current year or next year if month has passed
                            target_year = today.year
                            if target_month < today.month:
                                target_year = today.year + 1
                
                # If no specific month/year found, use relative terms
                if target_month is None:
                    target_month = today.month
                    target_year = today.year
                    
                    # Determine target month/year
                    if 'next month' in question_lower:
                        next_month = today + relativedelta(months=1)
                        target_month = next_month.month
                        target_year = next_month.year
                    elif 'next year' in question_lower:
                        target_year = today.year + 1
                    # "this month" and "this year" use current month/year (already set)
                
                logger.info(f"Searching for NDAs expiring in {target_month}/{target_year}")
                expiring_docs = metadata_service.find_documents_expiring_in_month(target_month, target_year)
                
                if expiring_docs:
                    # Format list for LLM
                    doc_list = []
                    for doc_info in expiring_docs:
                        doc_list.append(f"- {doc_info['company_name']}: expires {doc_info['expiration_date']}")
                    
                    month_name = datetime(target_year, target_month, 1).strftime("%B %Y")
                    additional_info = f"NDAs EXPIRING IN {month_name.upper()}:\n" + "\n".join(doc_list)
                    logger.info(f"Found {len(expiring_docs)} NDAs expiring in {month_name}")
                else:
                    month_name = datetime(target_year, target_month, 1).strftime("%B %Y")
                    additional_info = f"No NDAs found expiring in {month_name}."
                    logger.info(f"No NDAs expiring in {month_name}")
            
            # Check for cross-document comparison questions (multiple companies)
            elif ' and ' in question_lower or any(term in question_lower for term in ['both', 'same month', 'same year']):
                # Extract multiple company names
                company_names = self._extract_multiple_company_names(original_question)
                if len(company_names) >= 2:
                    logger.info(f"Cross-document comparison detected: {company_names}")
                    comparison_info = []
                    
                    for company_name in company_names:
                        logger.info(f"Searching for document matching company: {company_name}")
                        # Try lowercase first
                        doc_id = document_finder.find_best_document_match(company_name, use_fuzzy=True)
                        # If not found, try capitalized version
                        if not doc_id and company_name:
                            capitalized = company_name.capitalize()
                            logger.info(f"Trying capitalized version: {capitalized}")
                            doc_id = document_finder.find_best_document_match(capitalized, use_fuzzy=True)
                        # If still not found, try all caps (for acronyms like FANUC)
                        if not doc_id and company_name:
                            all_caps = company_name.upper()
                            logger.info(f"Trying all caps version: {all_caps}")
                            doc_id = document_finder.find_best_document_match(all_caps, use_fuzzy=True)
                        
                        if doc_id:
                            logger.info(f"✅ Found document for {company_name}: {doc_id[:8]}...")
                            # Get expiration info
                            expiration_answer = metadata_service.answer_expiration_date(doc_id)
                            if expiration_answer:
                                expiration_date = expiration_answer.text
                                # Calculate days/months
                                days = metadata_service.calculate_days_until_expiration(doc_id)
                                months = metadata_service.calculate_months_until_expiration(doc_id)
                                
                                info_parts = [f"{company_name}: expires {expiration_date}"]
                                if days is not None:
                                    info_parts.append(f"{days} days until expiration")
                                if months is not None:
                                    info_parts.append(f"{months} months until expiration")
                                
                                comparison_info.append(" - ".join(info_parts))
                                logger.info(f"Added comparison info for {company_name}: {expiration_date}")
                            else:
                                logger.warning(f"Could not get expiration date for {company_name} (doc_id: {doc_id[:8]}...)")
                        else:
                            logger.warning(f"❌ Could not find document for company: {company_name}")
                    
                    if comparison_info:
                        additional_info = "COMPARISON INFORMATION:\n" + "\n".join(comparison_info)
                        logger.info(f"Prepared comparison info for {len(comparison_info)} documents:\n{additional_info}")
                    else:
                        logger.warning("No comparison info generated - documents not found or missing expiration dates")
            
            # Single document questions
            elif document_id:
                # Check if asking about days
                if any(term in question_lower for term in ['how many days', 'days left', 'days until', 'days till']):
                    days = metadata_service.calculate_days_until_expiration(document_id)
                    if days is not None:
                        # Format days with context
                        if days < 0:
                            additional_info = f"The NDA expired {abs(days)} days ago (expired)."
                        elif days == 0:
                            additional_info = f"The NDA expires today (0 days remaining)."
                        else:
                            additional_info = f"Days until expiration: {days} days (calculated from today). Use this exact number in your answer."
                        logger.info(f"Calculated days until expiration: {days}")
                
                # Check if asking about months
                elif any(term in question_lower for term in ['how many months', 'months left', 'months until', 'months till']):
                    months = metadata_service.calculate_months_until_expiration(document_id)
                    if months is not None:
                        # Format months with context
                        if months < 0:
                            additional_info = f"The NDA expired {abs(months)} months ago (expired)."
                        elif months == 0:
                            additional_info = f"The NDA expires this month (0 months remaining)."
                        else:
                            additional_info = f"Months until expiration: {months} months (calculated from today). Use this exact number in your answer."
                        logger.info(f"Calculated months until expiration: {months}")
        
        # 6. Call LLM
        if self.llm_client is None:
            self.llm_client = get_llm_client()

        logger.info(f"Calling LLM with {len(context_chunks)} context chunks and {len(citations)} citations, conversational={is_conversational}")

        answer = await self.llm_client.generate_answer(
            query=original_question,
            context_chunks=context_chunks,
            citations=citations,
            use_conversational=is_conversational,
            additional_info=additional_info
        )

        logger.info(f"LLM returned answer: length={len(answer.text)}, answer={answer.text}")

        # 7. Context Quality Summary - Easy to review
        logger.info(f"")
        logger.info(f"═══════════════════════════════════════════════════════════════")
        logger.info(f"📊 CONTEXT QUALITY SUMMARY FOR REVIEW")
        logger.info(f"═══════════════════════════════════════════════════════════════")
        logger.info(f"Question: {question}")
        logger.info(f"Number of context chunks: {len(top_chunks)}")

        if top_chunks:
            top_scores = [r.get('score', 0) for r in top_chunks[:3]]
            avg_score = sum(top_scores) / len(top_scores) if top_scores else 0
            unique_clauses = len(set(r.get('clause_number') for r in top_chunks))
            unique_docs = len(set(r.get('doc_id') for r in top_chunks))

            logger.info(f"Average top 3 scores: {avg_score:.3f}")
            logger.info(f"Unique clauses: {unique_clauses}/{len(top_chunks)}")
            logger.info(f"Unique documents: {unique_docs}/{len(top_chunks)}")

            logger.info(f"\\nTop 5 Context Chunks:")
            for i, chunk in enumerate(top_chunks[:5]):
                logger.info(f"  {i+1}. doc_id: {chunk.get('doc_id')[:8]}..., clause: {chunk.get('clause_number')}, page: {chunk.get('page_num')}, score: {chunk.get('score', 0):.3f}")
                text_preview = chunk.get('text', '')[:150].replace('\\n', ' ')
                logger.info(f"     text: {text_preview}...")

            # If all chunks are same clause and low scores, context might be irrelevant
            if unique_clauses == 1 and avg_score < 0.15:
                logger.warning(f"⚠️  WARNING: All context chunks are from same clause (clause={top_chunks[0].get('clause_number')}) with low scores (avg={avg_score:.3f}). Context may be irrelevant to question.")

        logger.info(f"═══════════════════════════════════════════════════════════════")
        logger.info(f"")

        # 8. Post-process answer to extract structured response if needed
        # Skip structured extraction for conversational answers (they should remain natural)
        logger.info(f"Answer before post-processing: {answer.text}")

        if not is_conversational:
            # Only apply extraction for structured questions (not conversational)
            question_lower = question.lower()
            is_structured_question = any(word in question_lower for word in [
                'effective date', 'term', 'duration', 'how long', 'governing law',
                'jurisdiction', 'mutual', 'unilateral', 'parties to'
            ])

            if is_structured_question:
                answer.text = self._extract_structured_answer(question, answer.text)
                logger.info(f"Answer after structured extraction: {answer.text}")
            else:
                # For general questions, just clean up whitespace
                answer.text = answer.text.strip() if answer.text else ""
                logger.info(f"Answer after cleanup: {answer.text}")
        else:
            # For conversational answers, just clean up whitespace (keep natural language)
            answer.text = answer.text.strip() if answer.text else ""
            logger.info(f"Answer after cleanup (conversational): {answer.text}")

        # 9. Calculate confidence score for the answer
        # For metadata answers, confidence is already set above
        if not structured_answer:
            # Use LLM-based evaluation for chunk-based answers
            try:
                eval_result = await answer_evaluator.evaluate_answer_quality(
                    question=original_question,
                    answer=answer.text,
                    context_chunks=context_chunks
                )
                answer.confidence = eval_result.get("confidence", 0.7)
                answer.evaluation_reasoning = eval_result.get("reasoning", "")
                logger.info(f"Answer confidence: {answer.confidence:.2f} - {answer.evaluation_reasoning}")
            except Exception as e:
                logger.warning(f"Failed to evaluate answer confidence: {e}")
                # Fallback confidence based on answer quality heuristics
                if answer.text and len(answer.text) > 10 and "cannot find" not in answer.text.lower():
                    answer.confidence = 0.7
                    answer.evaluation_reasoning = "Confidence evaluation unavailable, using heuristic"
                else:
                    answer.confidence = 0.3
                    answer.evaluation_reasoning = "Answer appears incomplete or missing"

        return answer

    def _try_metadata_answer(self, question: str, document_id: str, logger) -> Optional[Answer]:
        """
        Try to answer question from structured metadata
        
        Args:
            question: User question
            document_id: Document UUID
            logger: Logger instance
            
        Returns:
            Answer if metadata can answer, None otherwise
        """
        # Normalize question first to fix typos like "effective data" -> "effective date"
        from api.services.query_normalizer import query_normalizer
        normalized_question = query_normalizer.normalize_query(question)
        question_lower = normalized_question.lower()
        
        # Use more specific detection to avoid false matches
        # Order matters: check most specific patterns first
        # IMPORTANT: Check parties and clause questions BEFORE term to avoid false matches
        
        # Check for parties FIRST (before term which might match "party to")
        if any(phrase in question_lower for phrase in ['who are the parties', 'parties to', 'party to the', 'between']):
            logger.info("Detected parties question, trying metadata")
            return metadata_service.answer_parties(document_id)
        
        # Check for clause questions - these should NOT use metadata, return None to fall back to chunks
        if any(phrase in question_lower for phrase in ['what does the', 'clause specify', 'clause state', 'clause say']):
            logger.info("Detected clause question, skipping metadata (will use chunk retrieval)")
            return None
        
        # Check for mutual/unilateral (before "term" which might match "mutual term")
        # Make sure it's actually asking about mutual/unilateral, not just containing the word
        if any(phrase in question_lower for phrase in ['is the', 'is this', 'is it', 'type of', 'mutual or', 'unilateral or']) and \
           any(term in question_lower for term in ['mutual', 'unilateral']):
            logger.info("Detected mutual/unilateral question, trying metadata")
            return metadata_service.answer_is_mutual(document_id)
        
        # Check for expiration/expiry date FIRST (before effective date, as "expire" might match "effective")
        if any(term in question_lower for term in ['expire', 'expiration date', 'expiry date', 'expires', 'when does it expire']):
            logger.info("Detected expiration_date question, trying metadata")
            return metadata_service.answer_expiration_date(document_id)
        
        # Check for effective date
        if any(term in question_lower for term in ['effective date', 'date of agreement', 'signed date', 'when was', 'when did']):
            logger.info("Detected effective_date question, trying metadata")
            return metadata_service.answer_effective_date(document_id)
        
        # Check for governing law
        if any(term in question_lower for term in ['governing law', 'governing state', 'jurisdiction', 'law applies', 'what law']):
            logger.info("Detected governing_law question, trying metadata")
            return metadata_service.answer_governing_law(document_id)
        
        # Check for term (but exclude survival, mutual mentions, and clause questions)
        # Only match if "term" or "duration" appears AND it's not a clause question
        if not any(phrase in question_lower for phrase in ['clause', 'what does', 'specify', 'state', 'say']) and \
           any(term in question_lower for term in ['term', 'duration', 'how long', 'expires', 'expiration', 'length']):
            # Exclude survival-related questions
            if 'survival' not in question_lower and 'after' not in question_lower:
                # Exclude if asking about mutual term (should be handled by mutual check above)
                if not ('mutual' in question_lower and 'term' in question_lower):
                    logger.info("Detected term question, trying metadata")
                    return metadata_service.answer_term(document_id, question)
        
        # Not a structured question or metadata not available
        return None

    async def _handle_cross_document_query(
        self,
        question: str,
        filters: Optional[Dict],
        max_context_chunks: int,
        query_info: Dict,
        logger
    ) -> Answer:
        """
        Handle cross-document queries by retrieving from multiple documents and synthesizing
        
        Args:
            question: User question
            filters: Optional filters (may be None for cross-doc queries)
            max_context_chunks: Maximum chunks per document
            query_info: Query understanding information
            logger: Logger instance
            
        Returns:
            Answer with citations from multiple documents
        """
        # For cross-document queries, don't filter by document_id
        # Retrieve chunks from multiple documents
        retrieval_query = query_info['transformed_query']
        
        # Get more chunks for cross-document synthesis
        search_results = self.search.hybrid_search(
            query=retrieval_query,
            k=max_context_chunks * 3,  # Get more chunks for cross-doc
            filters=None  # No document filter for cross-doc queries
        )
        
        logger.info(f"Cross-document search returned {len(search_results)} results from multiple documents")
        
        # Group results by document
        docs_results = {}
        for result in search_results:
            doc_id = result.get('doc_id')
            if doc_id not in docs_results:
                docs_results[doc_id] = []
            docs_results[doc_id].append(result)
        
        logger.info(f"Found chunks from {len(docs_results)} different documents")
        
        # Take top chunks from each document (balanced approach)
        chunks_per_doc = max(1, max_context_chunks // len(docs_results)) if docs_results else max_context_chunks
        top_chunks = []
        for doc_id, doc_results in docs_results.items():
            # Sort by score and take top chunks from this document
            doc_results.sort(key=lambda x: x.get('score', 0), reverse=True)
            top_chunks.extend(doc_results[:chunks_per_doc])
        
        # Sort all chunks by score
        top_chunks.sort(key=lambda x: x.get('score', 0), reverse=True)
        top_chunks = top_chunks[:max_context_chunks]
        
        logger.info(f"Selected {len(top_chunks)} chunks from {len(docs_results)} documents for cross-document synthesis")
        
        # Convert to Chunk objects
        context_chunks = self.search.get_chunks_for_answer(top_chunks)
        
        # Build citations
        citations = []
        for chunk in context_chunks:
            citation = Citation(
                doc_id=chunk.doc_id or '',
                clause_number=chunk.clause_number,
                page_num=chunk.page_num if chunk.page_num is not None else 0,
                span_start=chunk.span_start if chunk.span_start is not None else 0,
                span_end=chunk.span_end if chunk.span_end is not None else 0,
                source_uri=chunk.source_uri or '',
                excerpt=chunk.text
            )
            citations.append(citation)
        
        # Call LLM with cross-document prompt
        if self.llm_client is None:
            self.llm_client = get_llm_client()
        
        logger.info(f"Calling LLM for cross-document synthesis with {len(context_chunks)} chunks from {len(docs_results)} documents")
        
        answer = await self.llm_client.generate_answer(
            query=question,  # Use original question
            context_chunks=context_chunks,
            citations=citations
        )
        
        logger.info(f"Cross-document answer: {answer.text[:200]}")
        return answer

    def _assess_chunk_quality(self, chunks: List[Dict], question: str, logger) -> List[Dict]:
        """
        Assess chunk quality: relevance, completeness, answer presence
        
        Args:
            chunks: List of chunk dicts
            question: User question
            logger: Logger instance
            
        Returns:
            List of chunks with quality_score added
        """
        import re
        question_lower = question.lower()
        question_terms = set([t.lower() for t in question.split() if len(t) > 2])
        
        scored_chunks = []
        for chunk in chunks:
            chunk_text = chunk.get('text', '').lower()
            score = chunk.get('score', 0)
            
            # Quality factors
            relevance_score = 0.0
            completeness_score = 0.0
            answer_presence_score = 0.0
            
            # 1. Relevance: How many question terms appear in chunk?
            if question_terms and chunk_text:
                matching_terms = sum(1 for term in question_terms if term in chunk_text)
                relevance_score = matching_terms / len(question_terms) if question_terms else 0.0
            
            # 2. Completeness: Is chunk substantial enough?
            text_length = len(chunk.get('text', ''))
            if text_length >= 100:
                completeness_score = min(1.0, text_length / 500.0)  # Normalize to 500 chars
            else:
                completeness_score = text_length / 100.0  # Penalize very short chunks
            
            # 3. Answer presence: Does chunk contain answer indicators?
            # Check for structured answer patterns
            if any(term in question_lower for term in ['date', 'effective']):
                # Look for date patterns
                if re.search(r'\b(January|February|March|April|May|June|July|August|September|October|November|December)\s+\d{1,2},?\s+\d{4}\b', chunk_text):
                    answer_presence_score = 1.0
            elif any(term in question_lower for term in ['governing law', 'jurisdiction']):
                # Look for state names
                if any(state in chunk_text for state in ['delaware', 'california', 'new york', 'texas', 'florida']):
                    answer_presence_score = 0.8
            elif any(term in question_lower for term in ['term', 'duration']):
                # Look for duration patterns
                if re.search(r'\b\d+\s+(years?|months?)\b', chunk_text):
                    answer_presence_score = 0.8
            elif any(term in question_lower for term in ['mutual', 'unilateral']):
                # Look for type indicators
                if 'mutual' in chunk_text or 'unilateral' in chunk_text:
                    answer_presence_score = 0.8
            elif any(term in question_lower for term in ['parties', 'party']):
                # Look for company names
                if any(term in chunk_text for term in ['inc', 'llc', 'corp', 'company', 'corporation']):
                    answer_presence_score = 0.6
            elif any(term in question_lower for term in ['clause', 'specify']):
                # For clause questions, boost chunks that match the clause title
                chunk_clause_title = chunk.get('clause_title', '').lower() if chunk.get('clause_title') else ''
                if chunk_clause_title:
                    # Extract clause name from question
                    import re
                    clause_match = re.search(r'the\s+([^c]+?)\s+clause', question_lower)
                    if clause_match:
                        question_clause = clause_match.group(1).strip().lower()
                        # Check if chunk clause title matches or contains question clause
                        if question_clause in chunk_clause_title or chunk_clause_title in question_clause:
                            answer_presence_score = 1.0  # Strong match
                        elif any(word in chunk_clause_title for word in question_clause.split() if len(word) > 3):
                            answer_presence_score = 0.7  # Partial match
                    # Also boost if chunk has clause_number (it's a clause chunk)
                    if chunk.get('clause_number'):
                        answer_presence_score = max(answer_presence_score, 0.5)
            
            # Combine scores: weighted average
            # Original retrieval score (40%), relevance (30%), completeness (20%), answer presence (10%)
            quality_score = (
                0.4 * min(1.0, score) +  # Normalize score to [0, 1]
                0.3 * relevance_score +
                0.2 * completeness_score +
                0.1 * answer_presence_score
            )
            
            chunk['quality_score'] = quality_score
            chunk['relevance_score'] = relevance_score
            chunk['completeness_score'] = completeness_score
            chunk['answer_presence_score'] = answer_presence_score
            scored_chunks.append(chunk)
        
        # Sort by quality score (descending)
        scored_chunks.sort(key=lambda x: x.get('quality_score', 0), reverse=True)
        
        if scored_chunks:
            logger.info(f"Chunk quality assessment: top chunk quality={scored_chunks[0].get('quality_score', 0):.3f}, "
                       f"relevance={scored_chunks[0].get('relevance_score', 0):.3f}, "
                       f"completeness={scored_chunks[0].get('completeness_score', 0):.3f}")
        
        return scored_chunks

    def _single_query_search(
        self,
        question: str,
        filters: Optional[Dict],
        max_context_chunks: int,
        logger
    ) -> List[Dict]:
        """Single query strategy: one hybrid search with larger k"""
        search_results = self.search.hybrid_search(
            query=question,
            k=max_context_chunks * 5,  # Get more candidates for better context
            filters=filters
        )
        logger.info(f"Single query strategy: retrieved {len(search_results)} results")
        return search_results

    def _two_query_search(
        self,
        question: str,
        filters: Optional[Dict],
        max_context_chunks: int,
        logger
    ) -> List[Dict]:
        """Two-query strategy: find document, then find answer chunks"""
        # Query 1: Full question (finds relevant document)
        doc_results = self.search.hybrid_search(
            query=question,
            k=max_context_chunks * 2,
            filters=filters
        )
        
        # Identify top document from first query
        top_doc_id = None
        if doc_results:
            top_doc_id = doc_results[0].get('doc_id')
            logger.info(f"Top document from query: {top_doc_id[:8]}...")
        
        # Query 2: Extract answer topic and search for answer chunks FROM TOP DOCUMENT ONLY
        answer_topic = self._extract_answer_topic(question)
        if answer_topic and top_doc_id:
            logger.info(f"Answer topic: {answer_topic}, searching in top document {top_doc_id[:8]}...")
            # Search for answer topic (finds chunks across all docs)
            answer_results = self.search.hybrid_search(
                query=answer_topic,
                k=max_context_chunks * 3,  # Get more to ensure we find chunks from top doc
                filters=filters
            )
            # Filter to only chunks from top document
            top_doc_answer_chunks = [r for r in answer_results if r.get('doc_id') == top_doc_id]
            top_doc_doc_chunks = [r for r in doc_results if r.get('doc_id') == top_doc_id]
            logger.info(f"Found {len(top_doc_answer_chunks)} answer chunks and {len(top_doc_doc_chunks)} doc chunks in top document")
            
            # Combine: answer chunks from top doc + document chunks from top doc only
            # Deduplicate by chunk_id
            combined = {}
            for r in top_doc_answer_chunks + top_doc_doc_chunks:
                chunk_id = r.get('chunk_id')
                if chunk_id and (chunk_id not in combined or r.get('score', 0) > combined[chunk_id].get('score', 0)):
                    combined[chunk_id] = r
            
            search_results = list(combined.values())
            search_results.sort(key=lambda x: x.get('score', 0), reverse=True)
        else:
            # Fallback to single query
            search_results = doc_results
        
        logger.info(f"Two query strategy: retrieved {len(search_results)} results")
        return search_results

    def _extract_answer_topic(self, question: str) -> str:
        """Extract the answer topic from question (e.g., 'governing law', 'term', 'effective date')"""
        question_lower = question.lower()
        
        # Map question patterns to answer topics
        if any(term in question_lower for term in ['governing law', 'governing state', 'jurisdiction', 'law applies']):
            return "governing law"
        elif any(term in question_lower for term in ['term', 'duration', 'how long', 'expires', 'expiration']):
            return "term duration"
        elif any(term in question_lower for term in ['effective date', 'date of agreement', 'signed date']):
            return "effective date"
        elif any(term in question_lower for term in ['mutual', 'unilateral']):
            return "mutual unilateral"
        elif any(term in question_lower for term in ['parties', 'party to', 'who are']):
            return "parties"
        elif any(term in question_lower for term in ['confidential', 'confidentiality']):
            return "confidentiality"
        
        return None

    def _extract_multiple_company_names(self, question: str) -> List[str]:
        """
        Extract multiple company names from a comparison question.
        
        Examples:
            "does faunc and norris expire in the same month?" -> ["faunc", "norris"]
            "when do faunc and norris expire?" -> ["faunc", "norris"]
        """
        import re
        question_lower = question.lower()
        company_names = []
        
        # Pattern 1: "X and Y" where X and Y are company names
        # Look for words around "and"
        words = question.split()
        and_index = None
        for i, word in enumerate(words):
            if word.lower() == 'and':
                and_index = i
                break
        
        if and_index and and_index > 0 and and_index < len(words) - 1:
            # Extract word before "and" (likely first company)
            before_and = words[and_index - 1].rstrip('?.,').strip().lower()
            # Extract word after "and" (likely second company)
            after_and = words[and_index + 1].rstrip('?.,').strip().lower()
            
            # Skip common words
            skip_words = {'the', 'a', 'an', 'and', 'or', 'does', 'do', 'when', 'what', 'where', 
                         'how', 'many', 'days', 'months', 'expire', 'expires', 'expiration', 
                         'same', 'month', 'year', 'nda', 'agreement', 'both', 'all'}
            
            if before_and and before_and not in skip_words and len(before_and) > 2:
                company_names.append(before_and)
            if after_and and after_and not in skip_words and len(after_and) > 2:
                company_names.append(after_and)
        
        # Pattern 2: Try using document finder to extract company names
        # This handles capitalization variations better
        if len(company_names) < 2:
            # Import here to avoid circular dependency issues
            from api.services.document_finder import document_finder as doc_finder
            
            # Try to find all potential company names in the question
            # Look for capitalized words or common company name patterns
            skip_words = {'the', 'a', 'an', 'and', 'or', 'does', 'do', 'when', 'what', 'where', 
                         'how', 'many', 'days', 'months', 'expire', 'expires', 'expiration', 
                         'same', 'month', 'year', 'nda', 'agreement', 'both', 'all', 'in'}
            
            # Extract capitalized words
            capitalized = []
            for word in words:
                clean = word.rstrip('?.,').strip()
                # Accept if capitalized OR if it's a common company name pattern (3+ chars, not a skip word)
                is_capitalized = clean and (clean[0].isupper() or clean.isupper())
                is_valid = clean.lower() not in skip_words and len(clean) > 2
                
                if is_capitalized and is_valid:
                    capitalized.append(clean)
                elif not is_capitalized and is_valid and len(clean) > 3:
                    # Also try lowercase words that might be company names (like "faunc", "norris")
                    capitalized.append(clean)
            
            # If we found 2+ potential company names, use them
            if len(capitalized) >= 2:
                company_names = [c.lower() for c in capitalized[:2]]
        
        # Pattern 3: Try document finder's extract_company_name for each potential name
        # This helps with fuzzy matching
        if len(company_names) >= 2:
            # Verify these are actual company names by checking if documents exist
            import logging
            logger = logging.getLogger(__name__)
            
            # Import document finder here
            from api.services.document_finder import document_finder as doc_finder
            
            verified_names = []
            for name in company_names:
                doc_id = doc_finder.find_best_document_match(name, use_fuzzy=True)
                if doc_id:
                    verified_names.append(name)
                    logger.info(f"Verified company name '{name}' -> document {doc_id[:8]}...")
            
            if len(verified_names) >= 2:
                return verified_names
            elif len(verified_names) == 1:
                # Found one, try to find the other
                logger.info(f"Found one company ({verified_names[0]}), searching for second...")
        
        return company_names

    def _extract_structured_answer(self, question: str, answer_text: str) -> str:
        """
        Extract structured answer from LLM response
        Helps ensure answers match expected formats for competency testing
        """
        if not answer_text:
            return answer_text

        import re
        question_lower = question.lower()
        answer_clean = answer_text.strip()

        # For date questions, try to extract just the date
        if any(word in question_lower for word in ['date', 'effective', 'when']):
            # Look for date patterns like "September 5, 2025" or "July 16, 2025"
            date_pattern = r'([A-Z][a-z]+\s+\d{1,2},?\s+\d{4})'
            match = re.search(date_pattern, answer_clean)
            if match:
                return match.group(1)

        # For duration/term questions, extract just the duration
        if any(word in question_lower for word in ['term', 'duration', 'how long', 'months', 'years']):
            # Look for patterns like "3 years" or "36 months"
            duration_pattern = r'(\d+\s+(?:years?|months?))'
            match = re.search(duration_pattern, answer_clean, re.IGNORECASE)
            if match:
                return match.group(1)

        # For governing law questions, extract just the jurisdiction
        if any(word in question_lower for word in ['governing law', 'jurisdiction', 'law applies']):
            # Look for patterns like "State of Delaware" or "State of California"
            law_pattern = r'State of ([A-Z][a-z]+)'
            match = re.search(law_pattern, answer_clean)
            if match:
                return f"State of {match.group(1)}"

        # For mutual/unilateral questions, extract just the answer
        if any(word in question_lower for word in ['mutual', 'unilateral']):
            answer_lower = answer_clean.lower()
            if 'mutual' in answer_lower and 'unilateral' not in answer_lower:
                return 'mutual'
            elif 'unilateral' in answer_lower:
                return 'unilateral'

        # For other questions, don't truncate - return the full answer
        # The LLM prompt already asks for concise answers, so trust the LLM
        return answer_clean


# Global service instance
answer_service = AnswerService()
