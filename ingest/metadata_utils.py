"""Utility helpers for evaluating extracted metadata quality."""
from __future__ import annotations

from typing import Dict, List, Tuple


def compute_metadata_quality(metadata: Dict) -> Tuple[float, List[str]]:
    """Return (confidence_score, missing_fields) for extracted metadata."""
    missing: List[str] = []
    checks: List[bool] = []

    parties = metadata.get("parties") or []
    if len(parties) >= 2:
        checks.append(True)
    elif parties:
        missing.append("party_count")
        checks.append(False)
    else:
        missing.append("party_names")
        checks.append(False)

    if parties:
        if all(p.get("address") and p.get("address").strip() for p in parties):
            checks.append(True)
        else:
            missing.append("party_addresses")
            checks.append(False)

        if all(p.get("type") for p in parties):
            checks.append(True)
        else:
            missing.append("party_types")
            checks.append(False)

    effective_date = metadata.get("effective_date")
    if effective_date:
        checks.append(True)
    else:
        missing.append("effective_date")
        checks.append(False)

    governing_law = metadata.get("governing_law")
    if governing_law:
        checks.append(True)
    else:
        missing.append("governing_law")
        checks.append(False)

    term_months = metadata.get("term_months")
    if term_months:
        checks.append(True)
    else:
        missing.append("term_months")
        checks.append(False)

    mutuality = metadata.get("is_mutual")
    if mutuality is not None:
        checks.append(True)
    else:
        missing.append("mutuality")
        checks.append(False)

    total_checks = len(checks)
    score = round(sum(1 for c in checks if c) / total_checks, 2) if total_checks else 0.0
    missing_sorted = sorted(set(missing))
    return score, missing_sorted
