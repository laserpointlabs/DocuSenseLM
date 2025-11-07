#!/usr/bin/env python3
"""Validate extracted metadata against golden references."""
from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Tuple
import string

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from ingest.parser import parser  # type: ignore  # noqa: E402
from ingest.clause_extractor import clause_extractor  # type: ignore  # noqa: E402
from ingest.llm_refiner import refine_metadata  # type: ignore  # noqa: E402
from ingest.metadata_utils import compute_metadata_quality  # type: ignore  # noqa: E402


def normalize_name(name: str) -> str:
    translator = str.maketrans('', '', string.punctuation)
    return " ".join(name.lower().translate(translator).split())


def normalize_address(address: str | None) -> str | None:
    if not address:
        return None
    return " ".join(address.lower().split())


def normalize_governing_law(value: str | None) -> str | None:
    if not value:
        return None
    return value.strip().lower()


def normalize_date(value: Any) -> str | None:
    if not value:
        return None
    if isinstance(value, datetime):
        return value.date().isoformat()
    if isinstance(value, str):
        try:
            return datetime.fromisoformat(value.replace("Z", "")).date().isoformat()
        except ValueError:
            try:
                return datetime.strptime(value, "%Y-%m-%d").date().isoformat()
            except ValueError:
                return value.strip()
    return str(value)


def load_metadata(file_path: Path, use_llm: bool) -> Dict[str, Any]:
    parsed = parser.parse(str(file_path))
    pages = parsed.get("pages", [])
    full_text = "\n\n".join(page.get("text", "") for page in pages)

    extracted = clause_extractor.extract(full_text, pages)
    metadata = extracted.get("metadata", {})

    if use_llm:
        refined_metadata, _ = refine_metadata(metadata, full_text)
        metadata = refined_metadata

    return metadata


def compare_metadata(golden: Dict[str, Any], actual: Dict[str, Any]) -> List[str]:
    differences: List[str] = []

    golden_parties = golden.get("parties", []) or []
    actual_parties = actual.get("parties", []) or []

    golden_map = {normalize_name(p.get("name", "")): p for p in golden_parties if p.get("name")}
    actual_map = {normalize_name(p.get("name", "")): p for p in actual_parties if p.get("name")}

    for name_key, g_party in golden_map.items():
        if not name_key:
            continue
        if name_key not in actual_map:
            differences.append(f"Missing party: {g_party.get('name')}")
            continue
        a_party = actual_map[name_key]
        g_addr = normalize_address(g_party.get("address"))
        a_addr = normalize_address(a_party.get("address"))
        if g_addr and g_addr != a_addr:
            differences.append(
                f"Address mismatch for {g_party.get('name')}: expected '{g_party.get('address')}', got '{a_party.get('address')}'"
            )
        g_type = (g_party.get("type") or "").lower() or None
        a_type = (a_party.get("type") or "").lower() or None
        if g_type and g_type != a_type:
            differences.append(
                f"Party type mismatch for {g_party.get('name')}: expected '{g_type}', got '{a_type}'"
            )

    for name_key, a_party in actual_map.items():
        if name_key and name_key not in golden_map:
            differences.append(f"Unexpected party in extraction: {a_party.get('name')}")

    comparisons: List[Tuple[str, Any, Any, Any]] = [
        ("governing_law", golden.get("governing_law"), actual.get("governing_law"), normalize_governing_law),
        ("term_months", golden.get("term_months"), actual.get("term_months"), lambda x: x),
        ("is_mutual", golden.get("is_mutual"), actual.get("is_mutual"), lambda x: x),
        ("effective_date", golden.get("effective_date"), actual.get("effective_date"), normalize_date),
        ("survival_months", golden.get("survival_months"), actual.get("survival_months"), lambda x: x),
    ]

    for field, g_value, a_value, normalizer in comparisons:
        if g_value is None:
            continue
        if normalizer(g_value) != normalizer(a_value):
            differences.append(
                f"Field '{field}' mismatch: expected '{g_value}', got '{a_value}'"
            )

    return differences


def main() -> int:
    parser_obj = argparse.ArgumentParser(description="Validate extracted metadata against golden references")
    parser_obj.add_argument("--docs-dir", default="data", help="Directory containing NDA PDFs")
    parser_obj.add_argument(
        "--gold-dir",
        default="data/golden_metadata",
        help="Directory containing golden metadata JSON files",
    )
    parser_obj.add_argument(
        "--enable-llm",
        action="store_true",
        help="Enable LLM refinement when validating",
    )
    args = parser_obj.parse_args()

    docs_path = Path(args.docs_dir)
    gold_path = Path(args.gold_dir)

    if not docs_path.exists():
        print(f"Docs directory '{docs_path}' does not exist", file=sys.stderr)
        return 1

    if not gold_path.exists():
        print(f"Gold directory '{gold_path}' does not exist", file=sys.stderr)
        return 1

    if args.enable_llm:
        os.environ["ENABLE_LLM_REFINEMENT"] = "true"

    pdf_files = sorted(docs_path.glob("*.pdf"))
    if not pdf_files:
        print("No PDF files found; nothing to validate")
        return 0

    failures = 0

    for pdf_file in pdf_files:
        gold_file = gold_path / f"{pdf_file.name}.json"
        if not gold_file.exists():
            print(f"⚠️  Skipping {pdf_file.name}: no golden metadata ({gold_file.name})")
            continue

        with gold_file.open("r", encoding="utf-8") as fh:
            golden_metadata = json.load(fh)

        actual_metadata = load_metadata(pdf_file, use_llm=args.enable_llm)
        score, missing = compute_metadata_quality(actual_metadata)
        differences = compare_metadata(golden_metadata, actual_metadata)

        if differences:
            failures += 1
            print(f"❌ {pdf_file.name} - mismatches detected:")
            for diff in differences:
                print(f"   - {diff}")
            print(f"   confidence_score={score}, missing_fields={actual_metadata.get('missing_fields')}")
        else:
            print(f"✅ {pdf_file.name} - metadata matches expectations (confidence={score}, missing={missing})")

    if failures:
        print(f"\nValidation failed for {failures} document(s).")
        return 1

    print("\nAll available documents match their golden metadata.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
