import re
from collections import defaultdict
from dataclasses import dataclass, field
from decimal import Decimal, InvalidOperation
from typing import List, Optional


def normalize_ref(raw: str) -> str:
    if not raw:
        return ""
    return re.sub(r"[^a-z0-9]", "", raw.strip().lower())


def parse_decimal(value_str: str) -> Optional[Decimal]:
    if not value_str:
        return None
    cleaned = value_str.strip().upper()
    if cleaned in {"N/A", "NULL", "NONE", "-", ""}:
        return None
    cleaned = re.sub(r"[^\d.-]", "", cleaned)
    try:
        return Decimal(cleaned)
    except (InvalidOperation, ValueError):
        return None


@dataclass
class Discrepancy:
    reason: str          # MISSING_IN_SYSTEM_B | ORPHAN_IN_SYSTEM_B | DUPLICATE_IN_SYSTEM_B | VALUE_MISMATCH
    record_id: str       # canonical identifier (System A record_id where available)
    location_id: str
    org_id: str
    val_a: Optional[str]
    val_b: Optional[str]
    raw_ref_b: str = field(default="")   # original System B ref for audit trail


def reconcile(records_a: list, records_b: list, location_org_map: dict) -> List[Discrepancy]:
    """
    records_a: list of dicts with keys: record_id, location_id, raw_value
    records_b: list of dicts with keys: raw_record_ref, normalized_ref, location_id, raw_value
    location_org_map: {location_id: org_id}
    """
    discrepancies: List[Discrepancy] = []

    # Index System A by normalized id
    a_by_norm = {normalize_ref(r["record_id"]): r for r in records_a}

    # Index System B by normalized ref — one key may have multiple entries (duplicates)
    b_by_norm: dict = defaultdict(list)
    for b in records_b:
        b_by_norm[b["normalized_ref"]].append(b)

    matched_b_norms = set()

    # Pass 1 & 2 & 4: iterate System A
    for a in records_a:
        norm_id = normalize_ref(a["record_id"])
        org_id = location_org_map.get(a.get("location_id", ""), "UNKNOWN")
        b_entries = b_by_norm.get(norm_id, [])

        if not b_entries:
            # MISSING_IN_SYSTEM_B
            discrepancies.append(Discrepancy(
                reason="MISSING_IN_SYSTEM_B",
                record_id=a["record_id"],
                location_id=a.get("location_id", ""),
                org_id=org_id,
                val_a=a.get("raw_value"),
                val_b=None,
            ))
        elif len(b_entries) > 1:
            # DUPLICATE_IN_SYSTEM_B
            matched_b_norms.add(norm_id)
            discrepancies.append(Discrepancy(
                reason="DUPLICATE_IN_SYSTEM_B",
                record_id=a["record_id"],
                location_id=a.get("location_id", ""),
                org_id=org_id,
                val_a=a.get("raw_value"),
                val_b="; ".join(e.get("raw_value", "") for e in b_entries),
                raw_ref_b="; ".join(e.get("raw_record_ref", "") for e in b_entries),
            ))
        else:
            # Single match — check value parity
            matched_b_norms.add(norm_id)
            b = b_entries[0]
            val_a = parse_decimal(a.get("raw_value", ""))
            val_b = parse_decimal(b.get("raw_value", ""))
            if val_a != val_b:
                discrepancies.append(Discrepancy(
                    reason="VALUE_MISMATCH",
                    record_id=a["record_id"],
                    location_id=a.get("location_id", ""),
                    org_id=org_id,
                    val_a=a.get("raw_value"),
                    val_b=b.get("raw_value"),
                    raw_ref_b=b.get("raw_record_ref", ""),
                ))

    # Pass 3: orphans in System B
    for norm_ref, b_entries in b_by_norm.items():
        if norm_ref in matched_b_norms or norm_ref == "":
            continue
        if norm_ref in a_by_norm:
            continue  # already handled above
        for b in b_entries:
            org_id = location_org_map.get(b.get("location_id", ""), "UNKNOWN")
            discrepancies.append(Discrepancy(
                reason="ORPHAN_IN_SYSTEM_B",
                record_id=b.get("raw_record_ref", ""),
                location_id=b.get("location_id", ""),
                org_id=org_id,
                val_a=None,
                val_b=b.get("raw_value"),
                raw_ref_b=b.get("raw_record_ref", ""),
            ))

    return discrepancies
