"""LLM-assisted metadata refinement."""
from __future__ import annotations

import json
import logging
import os
import re
from typing import Any, Dict, Tuple

import httpx
from dateutil import parser as date_parser
from pydantic import BaseModel, ValidationError

from ingest.metadata_utils import compute_metadata_quality

logger = logging.getLogger(__name__)


class LLMParty(BaseModel):
    name: str
    address: str | None = None
    type: str | None = None


class LLMExtraction(BaseModel):
    parties: list[LLMParty] = []
    governing_law: str | None = None
    effective_date: str | None = None
    term_months: int | None = None
    is_mutual: bool | None = None
    notes: str | None = None


def _is_enabled() -> bool:
    return os.getenv("ENABLE_LLM_REFINEMENT", "false").lower() in {"1", "true", "yes"}


def _normalize_whitespace(value: str) -> str:
    """Collapse repeated whitespace and strip newlines."""
    return " ".join(value.replace("\n", " ").split())


def _postprocess_metadata(metadata: Dict[str, Any]) -> None:
    """Normalize party names/addresses and standardize other string fields."""
    parties = metadata.get("parties") or []
    for party in parties:
        name = party.get("name")
        if isinstance(name, str):
            cleaned_name = _normalize_whitespace(name)
            cleaned_name = cleaned_name.replace(" -", "-").replace("- ", "-")
            cleaned_name = re.sub(r"(?i)kidde[-\s]*fenwal", "Kidde-Fenwal", cleaned_name)
            party["name"] = cleaned_name

        address = party.get("address")
        if isinstance(address, str):
            cleaned_address = _normalize_whitespace(address)
            cleaned_address = cleaned_address.replace(" ,", ", ")
            cleaned_address = cleaned_address.replace(", ,", ", ")
            cleaned_address = re.sub(r",\s*,", ", ", cleaned_address)
            cleaned_address = cleaned_address.replace(",  ", ", ")
            cleaned_address = cleaned_address.replace(", China,", ", China ")
            if re.search(r"\bUSA\b", cleaned_address, re.IGNORECASE) is None and re.search(
                r"United States", cleaned_address, re.IGNORECASE
            ) is None:
                if re.search(r",[ ]*[A-Z]{2}[ ]*\d{5}(?:-\d{4})?$", cleaned_address):
                    cleaned_address = f"{cleaned_address}, USA"
            party["address"] = cleaned_address

        party_type = party.get("type")
        if isinstance(party_type, str):
            party["type"] = party_type.strip().lower() or None

    law = metadata.get("governing_law")
    if isinstance(law, str):
        metadata["governing_law"] = _normalize_whitespace(law)


def _should_refine(metadata: Dict[str, Any]) -> bool:
    if not metadata:
        return False
    threshold = float(os.getenv("LLM_REFINER_CONFIDENCE_THRESHOLD", "0.6"))
    if metadata.get("confidence_score", 0.0) < threshold:
        return True
    missing = metadata.get("missing_fields", []) or []
    if missing:
        return True
    parties = metadata.get("parties", [])
    if parties and any(not (p.get("address") or "") for p in parties):
        return True
    return False


def _extract_json_block(raw_text: str) -> str | None:
    if not raw_text:
        return None
    fenced = re.search(r"```json\s*(\{.*?\})\s*```", raw_text, re.DOTALL)
    if fenced:
        return fenced.group(1)
    match = re.search(r"\{.*\}", raw_text, re.DOTALL)
    if match:
        return match.group(0)
    return None


def refine_metadata(metadata: Dict[str, Any], document_text: str) -> Tuple[Dict[str, Any], Dict[str, Any]]:
    """Use a local LLM to enrich metadata when heuristics are insufficient."""
    if not _is_enabled():
        _postprocess_metadata(metadata)
        return metadata, {"applied": False, "reason": "llm_refinement_disabled"}

    if not _should_refine(metadata):
        _postprocess_metadata(metadata)
        return metadata, {"applied": False, "reason": "confidence_sufficient"}

    endpoint = os.getenv("LLM_ENDPOINT", "http://localhost:11434")
    model = os.getenv("LLM_EXTRACTION_MODEL") or os.getenv("OLLAMA_MODEL")
    if not model:
        raise ValueError("Either LLM_EXTRACTION_MODEL or OLLAMA_MODEL environment variable must be set")
    timeout = float(os.getenv("LLM_REFINER_TIMEOUT", "120"))

    metadata_for_prompt = json.loads(json.dumps(metadata, default=str))
    parties_for_prompt = metadata_for_prompt.get("parties") or []
    if parties_for_prompt:
        messy = len(parties_for_prompt) != 2 or any(" and " in (p.get("name") or "") for p in parties_for_prompt)
        if messy:
            metadata_for_prompt["parties"] = []

    existing_json = json.dumps(metadata_for_prompt, default=str, indent=2)
    text_snippet = document_text[:6000]

    prompt = f"""
You are extracting structured metadata from a Non-Disclosure Agreement (NDA).
Return valid JSON only (no commentary, no Markdown) matching this schema exactly:
{{
  "parties": [{{"name": str, "address": str | null, "type": str | null}}],
  "governing_law": str | null,
  "effective_date": str | null,  # Prefer ISO-8601 YYYY-MM-DD format
  "term_months": int | null,
  "is_mutual": bool | null
}}

Example output:
{{
  "parties": [
    {{"name": "Acme Corp", "address": "123 Main St, Springfield, IL 62701", "type": "disclosing"}},
    {{"name": "Globex LLC", "address": "400 Market St, Boston, MA 02110", "type": "receiving"}}
  ],
  "governing_law": "State of Delaware",
  "effective_date": "2024-05-01",
  "term_months": 36,
  "is_mutual": true
}}

Guidelines:
- Use information ONLY from the document excerpt.
- Party addresses must include street, city, state (and ZIP/country if present). Do not omit addresses when they appear.
- If a value truly does not appear, set it to null (do not guess).
- "type" should be "disclosing", "receiving", or null if not stated.
- If the existing extraction shows one entry that looks like multiple organisations combined (e.g., "Acme Corp Kidde LLC" or contains the word "and" between two company suffixes), split them into separate party entries and assign the appropriate address to each.

Existing (possibly incomplete) extraction:
{existing_json}

Document excerpt:
{text_snippet}
"""

    try:
        with httpx.Client(timeout=timeout) as client:
            response = client.post(
                f"{endpoint}/api/generate",
                json={
                    "model": model,
                    "prompt": prompt,
                    "stream": False,
                    "options": {
                        "temperature": 0,
                        "top_p": 0.1,
                    },
                },
            )
            response.raise_for_status()
            raw_response = response.json().get("response", "")
    except Exception as exc:  # pragma: no cover - network failure path
        logger.warning("LLM refinement failed: %s", exc)
        _postprocess_metadata(metadata)
        return metadata, {"applied": False, "reason": str(exc)}

    json_block = _extract_json_block(raw_response)
    if not json_block:
        logger.warning("LLM returned no JSON payload")
        _postprocess_metadata(metadata)
        return metadata, {"applied": False, "reason": "no_json"}

    try:
        parsed = json.loads(json_block)
        refined = LLMExtraction.parse_obj(parsed)
    except (json.JSONDecodeError, ValidationError) as exc:
        logger.warning("Invalid LLM JSON payload: %s", exc)
        _postprocess_metadata(metadata)
        return metadata, {"applied": False, "reason": "invalid_json", "raw_response": raw_response}

    before_missing = metadata.get("missing_fields", [])
    before_confidence = metadata.get("confidence_score", 0.0)
    applied = False

    parties = metadata.get("parties", [])
    if refined.parties:
        parties = []
        for llm_party in refined.parties:
            name = (llm_party.name or "").strip()
            if not name:
                continue
            parties.append(
                {
                    "name": name,
                    "type": (llm_party.type or None) and llm_party.type.strip().lower(),
                    "address": (llm_party.address or None) and llm_party.address.strip(),
                }
            )
        metadata["parties"] = parties
        applied = True

    if refined.governing_law and not metadata.get("governing_law"):
        metadata["governing_law"] = refined.governing_law.strip()
        applied = True

    if refined.term_months and not metadata.get("term_months"):
        metadata["term_months"] = int(refined.term_months)
        applied = True

    if refined.is_mutual is not None and metadata.get("is_mutual") is None:
        metadata["is_mutual"] = bool(refined.is_mutual)
        applied = True

    if refined.effective_date and not metadata.get("effective_date"):
        try:
            metadata["effective_date"] = date_parser.parse(refined.effective_date)
            applied = True
        except (ValueError, TypeError):  # pragma: no cover - parse failure
            pass

    _postprocess_metadata(metadata)

    # Recompute quality metrics
    confidence, missing = compute_metadata_quality(metadata)
    metadata["confidence_score"] = confidence
    metadata["missing_fields"] = missing
    if applied:
        metadata["extraction_method"] = "heuristic+llm"

    info = {
        "applied": applied,
        "model": model,
        "raw_response": raw_response,
        "confidence_before": before_confidence,
        "confidence_after": confidence,
        "missing_before": before_missing,
        "missing_after": missing,
    }
    return metadata, info
