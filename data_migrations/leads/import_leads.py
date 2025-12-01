import os
import django
import pandas as pd
import phonenumbers
from django.utils.dateparse import parse_datetime
from zoneinfo import ZoneInfo
from django.utils import timezone
from decimal import Decimal

# ⚙️ Init Django
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "tds.settings.prod")
django.setup()

from api.leads.models import Lead
from api.clients.models import Client
from api.users.models import User
from api.lead_status.models import LeadStatus
from api.comments.models import Comment
from api.contracts.models import Contract
from api.services.models import Service
from api.payments.models import PaymentReceipt

# --- CONFIG ---
INPUT_CSV = "leads_with_contracts.csv"
OUTPUT_CSV = "leads_with_contracts.csv"
SKIPPED_CSV = "skipped_leads.csv"
PARIS_TZ = ZoneInfo("Europe/Paris")


def parse_dt_safe(value):
    if pd.isna(value) or not str(value).strip():
        return None
    dt = parse_datetime(str(value))
    if dt and dt.tzinfo is None:
        dt = dt.replace(tzinfo=PARIS_TZ)
    return dt


def clean_phone(raw_value: str) -> str | None:
    if not raw_value or str(raw_value).lower() in ("nan", "none"):
        return None

    raw = str(raw_value).strip()
    if raw.endswith(".0"):
        raw = raw[:-2]
    if isinstance(raw_value, float):
        raw = str(int(raw_value))

    raw = raw.replace(" ", "").replace(".", "").replace(",", "")

    try:
        if raw.startswith("0") and len(raw) >= 9:
            raw = "+33" + raw[1:]
        elif len(raw) == 9 and raw[0] in ["6", "7"]:
            raw = "+33" + raw
        elif raw.startswith("33") and not raw.startswith("+"):
            raw = "+" + raw
        elif raw.startswith("359"):  # Bulgarie
            raw = "+" + raw
        elif raw.startswith("93"):   # Afghanistan
            raw = "+" + raw
        elif not raw.startswith("+"):
            raw = "+33" + raw

        num = phonenumbers.parse(raw, None)
        if phonenumbers.is_valid_number(num):
            return phonenumbers.format_number(num, phonenumbers.PhoneNumberFormat.E164)
    except Exception:
        pass
    return None


def create_contract(client, collaborator, service_id, amount, contract_date):
    if pd.isna(service_id) or str(service_id).strip() in ("", "nan", "none") or amount <= 0:
        print(f"ℹ️ Aucun contrat à créer → (service_id={service_id}, montant={amount})")
        return None

    try:
        service = Service.objects.get(id=int(service_id))
    except (Service.DoesNotExist, ValueError):
        print(f"⚠️ Service introuvable (id={service_id}) → contrat ignoré")
        return None

    existing_contract = Contract.objects.filter(
        client=client,
        service=service,
        amount_due=amount,
        is_signed=True
    ).first()

    if existing_contract:
        updated = False
        if not existing_contract.created_by and collaborator:
            existing_contract.created_by = collaborator
            updated = True
        if not existing_contract.contract_url:
            existing_contract.contract_url = f"https://fake.url/contracts/{client.id}.pdf"
            updated = True
        if updated:
            existing_contract.save(update_fields=["created_by", "contract_url"])
            print(f"♻️ Contrat existant mis à jour → Client {client.id} / "
                  f"Service={service.label} / Contrat #{existing_contract.id}")
        else:
            print(f"⚠️ Contrat déjà existant (aucune mise à jour nécessaire) → "
                  f"Client {client.id} / Service={service.label} / Contrat #{existing_contract.id}")
        return existing_contract
    else:
        new_contract = Contract.objects.create(
            client=client,
            created_by=collaborator,
            service=service,
            amount_due=amount,
            created_at=contract_date or timezone.now(),
            is_signed=True,
            contract_url=f"https://fake.url/contracts/{client.id}.pdf"
        )
        print(f"✅ Nouveau contrat créé → Client {client.id} / "
              f"Service={service.label} / Montant={amount} → Contrat #{new_contract.id}")
        return new_contract


def create_payments(client, contract, row, collaborator):
    for i in range(1, 5):
        amount = row.get(f"payment_{i}_amount")
        date = parse_dt_safe(row.get(f"payment_{i}_date"))
        method = row.get(f"payment_{i}_method")

        try:
            amount = Decimal(str(amount).replace(",", ".") or "0")
        except Exception:
            amount = Decimal("0")

        if amount <= 0:
            continue

        receipt = PaymentReceipt.objects.create(
            client=client,
            contract=contract,
            amount=amount,
            mode=method,
            payment_date=date or timezone.now(),
            created_by=collaborator,
            receipt_url=f"https://fake.url/receipts/{client.id}_{contract.id}_{i}.pdf"
        )
        print(f"💳 Paiement créé → Client {client.id} / Contrat {contract.id} / "
              f"Montant={amount}€ / Mode={method} / Reçu #{receipt.id}")


def import_leads(csv_path: str):
    df = pd.read_csv(csv_path, encoding="utf-8-sig")

    if "status_id" not in df.columns or "collaborator_id" not in df.columns:
        raise ValueError("❌ Le CSV doit contenir les colonnes 'status_id' et 'collaborator_id'")

    existing_emails = set(Lead.objects.exclude(email=None).values_list("email", flat=True))
    existing_phones = set(Lead.objects.exclude(phone=None).values_list("phone", flat=True))

    leads_to_create = []
    clients_to_create = []
    skipped_leads = []

    last_created_at = None

    if "client_id" not in df.columns:
        df["client_id"] = pd.Series([None] * len(df), dtype="string")
    else:
        df["client_id"] = df["client_id"].astype("string")

    for idx, row in df.iterrows():
        first_name = str(row.get("first_name", "")).strip().capitalize()
        last_name = str(row.get("last_name", "")).strip().capitalize()
        email = str(row.get("email", "")).strip().lower() or None
        phone = clean_phone(row.get("phone"))
        created_at = parse_dt_safe(row.get("created_at"))
        appointment_date = parse_dt_safe(row.get("appointment_date"))

        if not created_at:
            created_at = (last_created_at + pd.Timedelta(days=1)) if last_created_at else timezone.now()
        last_created_at = created_at

        if not phone:
            skipped_leads.append({
                "first_name": first_name,
                "last_name": last_name,
                "email": email,
                "reason": "Téléphone manquant"
            })
            print(f"⏭️ Ignoré (pas de téléphone) : {first_name} {last_name} ({email})")
            continue

        existing_lead = None
        if email:
            existing_lead = Lead.objects.filter(email=email).first()
        if not existing_lead and phone:
            existing_lead = Lead.objects.filter(phone=phone).first()

        collaborator = None
        collaborator_id = str(row.get("collaborator_id")).strip()
        if collaborator_id and collaborator_id.lower() not in ("nan", "none", ""):
            try:
                collaborator = User.objects.get(id=collaborator_id)
            except User.DoesNotExist:
                print(f"⚠️ Collaborateur introuvable : {collaborator_id}")

        if existing_lead:
            client, _ = Client.objects.get_or_create(lead=existing_lead)
            df.at[idx, "client_id"] = str(client.id)

            amount = Decimal(str(row.get("montant", "0")).replace(",", ".") or "0")
            contract_date = parse_dt_safe(row.get("contract_date"))
            contract = create_contract(client, collaborator, row.get("service_id"), amount, contract_date)
            if contract:
                create_payments(client, contract, row, collaborator)
            continue

        try:
            status = LeadStatus.objects.get(id=row.get("status_id"))
        except LeadStatus.DoesNotExist:
            print(f"⚠️ Statut introuvable : {row.get('status_id')}, ignoré")
            continue

        commentaire = str(row.get("commentaires", "")).strip()

        lead = Lead(
            first_name=first_name,
            last_name=last_name,
            email=email,
            phone=phone,
            status=status,
            created_at=created_at,
            appointment_date=appointment_date,
        )
        leads_to_create.append((lead, collaborator, commentaire, idx))

        existing_emails.add(email)
        existing_phones.add(phone)

    created_leads = Lead.objects.bulk_create([l for l, _, _, _ in leads_to_create])

    for (lead, collaborator, commentaire, idx), created_lead in zip(leads_to_create, created_leads):
        if collaborator:
            created_lead.assigned_to.add(collaborator)

        client = Client.objects.create(lead=created_lead)
        df.at[idx, "client_id"] = str(client.id)
        clients_to_create.append(client)

        if commentaire and collaborator:
            Comment.objects.create(
                lead=created_lead,
                author=collaborator,
                content=commentaire
            )

        amount = Decimal(str(df.at[idx, "montant"]).replace(",", ".") or "0")
        contract_date = parse_dt_safe(df.at[idx, "contract_date"])
        contract = create_contract(client, collaborator, df.at[idx, "service_id"], amount, contract_date)
        if contract:
            create_payments(client, contract, df.loc[idx], collaborator)

    df.to_csv(OUTPUT_CSV, index=False, encoding="utf-8-sig")

    if skipped_leads:
        pd.DataFrame(skipped_leads).to_csv(SKIPPED_CSV, index=False, encoding="utf-8-sig")
        print(f"⚠️ {len(skipped_leads)} leads ignorés sans téléphone. Liste → {SKIPPED_CSV}")

    print(f"\n✅ Import terminé : {len(created_leads)} nouveaux leads créés, "
          f"{len(clients_to_create)} clients")


if __name__ == "__main__":
    import_leads(INPUT_CSV)