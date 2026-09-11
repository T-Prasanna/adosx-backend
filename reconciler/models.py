from django.db import models


class Location(models.Model):
    location_id = models.CharField(max_length=50, unique=True)
    location_name = models.CharField(max_length=200)
    org_id = models.CharField(max_length=50)

    def __str__(self):
        return f"{self.location_id} ({self.org_id})"


class SystemARecord(models.Model):
    record_id = models.CharField(max_length=100, unique=True)
    location = models.ForeignKey(Location, null=True, on_delete=models.SET_NULL)
    event_date = models.CharField(max_length=50, blank=True)  # stored raw; invalid dates survive
    raw_value = models.CharField(max_length=100, blank=True)
    status = models.CharField(max_length=50, blank=True)

    def __str__(self):
        return self.record_id


class SystemBEntry(models.Model):
    raw_record_ref = models.CharField(max_length=100)          # original, unmodified
    normalized_ref = models.CharField(max_length=100, db_index=True)  # canonical key for matching
    location = models.ForeignKey(Location, null=True, on_delete=models.SET_NULL)
    event_date = models.CharField(max_length=50, blank=True)
    raw_value = models.CharField(max_length=100, blank=True)
    status = models.CharField(max_length=50, blank=True)

    def __str__(self):
        return f"{self.raw_record_ref} -> {self.normalized_ref}"
