import csv
import os
import re
from django.core.management.base import BaseCommand
from reconciler.models import Location, SystemARecord, SystemBEntry


def normalize_ref(raw: str) -> str:
    """Strip whitespace, dashes, underscores; lowercase. 'REC-042', ' rec_042 ', 'REC042' all -> 'rec042'."""
    if not raw:
        return ""
    return re.sub(r"[^a-z0-9]", "", raw.strip().lower())


class Command(BaseCommand):
    help = "Import locations.csv, system_a.csv, system_b.csv into the database."

    def add_arguments(self, parser):
        parser.add_argument(
            "--data-dir",
            default=os.path.join(os.path.dirname(__file__), "../../../../data"),
            help="Path to directory containing the three CSV files.",
        )

    def handle(self, *args, **options):
        data_dir = os.path.abspath(options["data_dir"])
        self._import_locations(os.path.join(data_dir, "locations.csv"))
        self._import_system_a(os.path.join(data_dir, "system_a.csv"))
        self._import_system_b(os.path.join(data_dir, "system_b.csv"))
        self.stdout.write(self.style.SUCCESS("Import complete."))

    def _import_locations(self, path):
        Location.objects.all().delete()
        count = 0
        with open(path, newline="", encoding="utf-8-sig") as f:
            for row in csv.DictReader(f):
                loc_id = row.get("location_id", "").strip()
                if not loc_id:
                    self.stdout.write(f"  [SKIP] locations row missing location_id: {row}")
                    continue
                Location.objects.update_or_create(
                    location_id=loc_id,
                    defaults={
                        "location_name": row.get("location_name", "").strip(),
                        "org_id": row.get("org_id", "").strip(),
                    },
                )
                count += 1
        self.stdout.write(f"  Locations loaded: {count}")

    def _import_system_a(self, path):
        SystemARecord.objects.all().delete()
        loc_map = {loc.location_id: loc for loc in Location.objects.all()}
        count, skipped = 0, 0
        with open(path, newline="", encoding="utf-8-sig") as f:
            for row in csv.DictReader(f):
                record_id = row.get("record_id", "").strip()
                if not record_id:
                    self.stdout.write(f"  [SKIP] system_a row missing record_id: {row}")
                    skipped += 1
                    continue
                loc_id = row.get("location_id", "").strip()
                location = loc_map.get(loc_id)
                if not location:
                    self.stdout.write(f"  [WARN] system_a {record_id}: unknown location '{loc_id}', stored without FK")
                SystemARecord.objects.update_or_create(
                    record_id=record_id,
                    defaults={
                        "location": location,
                        "event_date": row.get("event_date", "").strip(),
                        "raw_value": row.get("value", "").strip(),
                        "status": row.get("status", "").strip(),
                    },
                )
                count += 1
        self.stdout.write(f"  System A loaded: {count}, skipped: {skipped}")

    def _import_system_b(self, path):
        SystemBEntry.objects.all().delete()
        loc_map = {loc.location_id: loc for loc in Location.objects.all()}
        count, skipped = 0, 0
        with open(path, newline="", encoding="utf-8-sig") as f:
            for row in csv.DictReader(f):
                raw_ref = row.get("record_ref", "").strip()
                norm = normalize_ref(raw_ref)
                if not norm:
                    self.stdout.write(f"  [SKIP] system_b row with empty/unparseable record_ref: {row}")
                    skipped += 1
                    continue
                loc_id = row.get("location_id", "").strip()
                location = loc_map.get(loc_id)
                if not location:
                    self.stdout.write(f"  [WARN] system_b ref '{raw_ref}': unknown location '{loc_id}'")
                SystemBEntry.objects.create(
                    raw_record_ref=raw_ref,
                    normalized_ref=norm,
                    location=location,
                    event_date=row.get("event_date", "").strip(),
                    raw_value=row.get("value", "").strip(),
                    status=row.get("status", "").strip(),
                )
                count += 1
        self.stdout.write(f"  System B loaded: {count}, skipped: {skipped}")
