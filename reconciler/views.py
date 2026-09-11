from django.http import JsonResponse
from reconciler.models import Location, SystemARecord, SystemBEntry
from reconciler.services.comparator import reconcile


def _build_location_org_map():
    return {loc.location_id: loc.org_id for loc in Location.objects.all()}


def _records_a():
    return [
        {
            "record_id": r.record_id,
            "location_id": r.location.location_id if r.location else "",
            "raw_value": r.raw_value,
        }
        for r in SystemARecord.objects.select_related("location").all()
    ]


def _records_b():
    return [
        {
            "raw_record_ref": e.raw_record_ref,
            "normalized_ref": e.normalized_ref,
            "location_id": e.location.location_id if e.location else "",
            "raw_value": e.raw_value,
        }
        for e in SystemBEntry.objects.select_related("location").all()
    ]


def orgs_list(request):
    orgs = sorted(Location.objects.values_list("org_id", flat=True).distinct())
    return JsonResponse({"orgs": list(orgs)})


def discrepancies(request):
    org_id = request.GET.get("org_id", "").strip()
    if not org_id:
        return JsonResponse({"error": "org_id query parameter is required"}, status=400)

    reason_filter = request.GET.get("reason", "").strip().upper()

    loc_org_map = _build_location_org_map()
    results = reconcile(_records_a(), _records_b(), loc_org_map)

    # Tenant boundary: only return rows belonging to the requested org
    results = [d for d in results if d.org_id == org_id]

    if reason_filter and reason_filter != "ALL":
        results = [d for d in results if d.reason == reason_filter]

    return JsonResponse({
        "results": [
            {
                "reason": d.reason,
                "record_id": d.record_id,
                "location_id": d.location_id,
                "org_id": d.org_id,
                "val_a": d.val_a,
                "val_b": d.val_b,
                "raw_ref_b": d.raw_ref_b,
            }
            for d in results
        ]
    })
