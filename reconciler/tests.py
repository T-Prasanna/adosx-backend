from django.test import TestCase
from reconciler.services.comparator import reconcile, normalize_ref, parse_decimal
from decimal import Decimal


def make_a(record_id, value="100.00", location_id="LOC-1"):
    return {"record_id": record_id, "location_id": location_id, "raw_value": value}


def make_b(ref, value="100.00", location_id="LOC-1"):
    from reconciler.services.comparator import normalize_ref as nr
    return {"raw_record_ref": ref, "normalized_ref": nr(ref), "location_id": location_id, "raw_value": value}


LOC_MAP = {"LOC-1": "ORG-1", "LOC-2": "ORG-2"}


class NormalizeRefTests(TestCase):
    def test_strips_whitespace_and_dashes(self):
        self.assertEqual(normalize_ref(" REC-042 "), "rec042")

    def test_strips_underscores(self):
        self.assertEqual(normalize_ref("rec_042"), "rec042")

    def test_empty_string(self):
        self.assertEqual(normalize_ref(""), "")

    def test_already_clean(self):
        self.assertEqual(normalize_ref("REC001"), "rec001")


class ParseDecimalTests(TestCase):
    def test_plain_number(self):
        self.assertEqual(parse_decimal("100.00"), Decimal("100.00"))

    def test_currency_symbol(self):
        self.assertEqual(parse_decimal("$1,200.50"), Decimal("1200.50"))

    def test_na_returns_none(self):
        self.assertIsNone(parse_decimal("N/A"))

    def test_blank_returns_none(self):
        self.assertIsNone(parse_decimal(""))

    def test_null_string_returns_none(self):
        self.assertIsNone(parse_decimal("NULL"))


class ReconcileTests(TestCase):

    def test_detects_missing_in_system_b(self):
        results = reconcile([make_a("REC-01")], [], LOC_MAP)
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].reason, "MISSING_IN_SYSTEM_B")
        self.assertEqual(results[0].record_id, "REC-01")
        self.assertEqual(results[0].val_b, None)

    def test_detects_orphan_in_system_b(self):
        results = reconcile([], [make_b("REC-999")], LOC_MAP)
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].reason, "ORPHAN_IN_SYSTEM_B")
        self.assertEqual(results[0].val_a, None)

    def test_detects_duplicate_in_system_b(self):
        # Two B entries with refs that normalize to the same key
        results = reconcile(
            [make_a("REC-01")],
            [make_b("REC-01"), make_b(" rec-01 ")],
            LOC_MAP,
        )
        reasons = [r.reason for r in results]
        self.assertIn("DUPLICATE_IN_SYSTEM_B", reasons)

    def test_detects_value_mismatch(self):
        results = reconcile([make_a("REC-01", "100.00")], [make_b("REC-01", "200.00")], LOC_MAP)
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].reason, "VALUE_MISMATCH")
        self.assertEqual(results[0].val_a, "100.00")
        self.assertEqual(results[0].val_b, "200.00")

    def test_no_discrepancy_when_values_match(self):
        results = reconcile([make_a("REC-01", "100.00")], [make_b("REC-01", "100.00")], LOC_MAP)
        self.assertEqual(results, [])

    def test_messy_ref_normalizes_and_matches(self):
        """rec_042 in System B should match REC-042 in System A — not an orphan."""
        results = reconcile([make_a("REC-042")], [make_b("rec_042")], LOC_MAP)
        self.assertEqual(results, [])

    def test_unparseable_value_treated_as_none_causes_mismatch(self):
        """N/A in System B vs a real number in System A is a VALUE_MISMATCH."""
        results = reconcile([make_a("REC-01", "100.00")], [make_b("REC-01", "N/A")], LOC_MAP)
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].reason, "VALUE_MISMATCH")

    def test_tenant_boundary_isolation(self):
        """Discrepancies for ORG-2 must not appear when filtering for ORG-1."""
        a_records = [make_a("REC-01", location_id="LOC-1"), make_a("REC-02", location_id="LOC-2")]
        b_records = [make_b("REC-01", location_id="LOC-1")]
        # REC-02 (LOC-2 / ORG-2) is missing from B
        all_results = reconcile(a_records, b_records, LOC_MAP)
        org1_results = [r for r in all_results if r.org_id == "ORG-1"]
        org2_results = [r for r in all_results if r.org_id == "ORG-2"]
        self.assertEqual(org1_results, [])
        self.assertEqual(len(org2_results), 1)
        self.assertEqual(org2_results[0].reason, "MISSING_IN_SYSTEM_B")
