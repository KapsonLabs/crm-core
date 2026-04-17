from rest_framework import serializers


class DraftVersionCreateSerializer(serializers.Serializer):
    kpi_id = serializers.UUIDField()
    formula = serializers.CharField()


class VersionTransitionSerializer(serializers.Serializer):
    comment = serializers.CharField(required=False, allow_blank=True)


class ExecutionTriggerSerializer(serializers.Serializer):
    PERIOD_CHOICES = (
        ("daily", "daily"),
        ("weekly", "weekly"),
        ("monthly", "monthly"),
        ("quarterly", "quarterly"),
        ("yearly", "yearly"),
        ("rolling", "rolling"),
        ("ytd", "ytd"),
    )

    kpi_id = serializers.UUIDField()
    version = serializers.IntegerField(required=False, min_value=1)
    kind = serializers.ChoiceField(choices=PERIOD_CHOICES)
    start = serializers.DateField()
    end = serializers.DateField()
    trigger = serializers.CharField(default="manual")
    run_async = serializers.BooleanField(default=True)

    def validate(self, attrs):
        if attrs["start"] > attrs["end"]:
            raise serializers.ValidationError("start must be on or before end.")
        return attrs


class SnapshotQuerySerializer(serializers.Serializer):
    kpi_id = serializers.UUIDField()
    start_date = serializers.DateField(required=False)
    end_date = serializers.DateField(required=False)

    def validate(self, attrs):
        start = attrs.get("start_date")
        end = attrs.get("end_date")
        if start and end and start > end:
            raise serializers.ValidationError("start_date must be on or before end_date.")
        return attrs
