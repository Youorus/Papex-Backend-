# api/services/migrations/0003_fix_codes_from_label.py
from django.db import migrations

def forwards(apps, schema_editor):
    Service = apps.get_model("services", "Service")

    import re, unicodedata
    def code_from_label(label: str) -> str:
        s = unicodedata.normalize("NFKD", label)
        s = "".join(c for c in s if unicodedata.category(c) != "Mn")
        s = re.sub(r"[^0-9A-Za-z]+", "_", s)
        s = re.sub(r"_+", "_", s).strip("_")
        return s.upper()

    seen = set()
    existing = set(Service.objects.values_list("code", flat=True))

    for svc in Service.objects.all().order_by("id"):
        target = code_from_label(svc.label)
        if svc.code == target:
            seen.add(target); continue
        final, i = target, 2
        while final in existing or final in seen:
            final = f"{target}_{i}"; i += 1
        Service.objects.filter(pk=svc.pk).update(code=final)
        seen.add(final)

class Migration(migrations.Migration):
    dependencies = [("services", "0002_alter_service_label")]
    operations = [migrations.RunPython(forwards, migrations.RunPython.noop)]