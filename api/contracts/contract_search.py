from datetime import date, datetime, time
from decimal import Decimal
from typing import Optional

from django.db.models import (
    BooleanField,
    Case,
    Count,
    DecimalField,
    ExpressionWrapper,
    F,
    Max,
    Min,
    Q,
    Sum,
    Value,
    When,
)
from django.db.models.functions import Coalesce, Greatest
from django.utils import timezone
from django.utils.dateparse import parse_date, parse_datetime
from django.utils.timezone import get_current_timezone, is_naive, make_aware
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.viewsets import ViewSet
from io import BytesIO
from django.http import HttpResponse
from rest_framework.decorators import action
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import cm
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, PageBreak

from api.contracts.models import Contract
from rest_framework.renderers import BaseRenderer


class PDFRenderer(BaseRenderer):
    media_type = "application/pdf"
    format = "pdf"
    charset = None


# ─── Helpers module-level ────────────────────────────────────────────────────

def _parse_iso_any(dt: Optional[str]) -> Optional[object]:
    if not dt:
        return None
    return parse_datetime(dt) or parse_date(dt)


def _dec(v: Optional[Decimal]) -> float:
    return float(v or Decimal("0.00"))


def _normalize_avec_sans(value: Optional[str]) -> Optional[str]:
    if not value:
        return None
    v = value.strip().lower()
    if v in {"avec", "oui", "with", "true", "1"}:
        return "avec"
    if v in {"sans", "non", "without", "false", "0"}:
        return "sans"
    return None


def _to_dec(v):
    return ContractSearchService._to_dec(v)


def _to_int_or_str(v):
    return ContractSearchService._to_int_or_str(v)


def _to_aware(dt_or_d: Optional[object], end_of_day: bool = False) -> Optional[datetime]:
    if dt_or_d is None:
        return None
    tz = get_current_timezone()
    if isinstance(dt_or_d, date) and not isinstance(dt_or_d, datetime):
        dtime = datetime.combine(
            dt_or_d, time(23, 59, 59, 999999) if end_of_day else time(0, 0, 0, 0)
        )
        return make_aware(dtime, timezone=tz)
    if is_naive(dt_or_d):
        return make_aware(dt_or_d, timezone=tz)
    return dt_or_d


# ─────────────────────────────────────────────────────────────────────────────
class ContractSearchService:
    """
    Service de recherche et filtrage des contrats.

    🔥 CONVENTION D'ANNOTATION :
    Les champs calculés qui portent le même nom qu'une @property du modèle Contract
    (amount_paid, net_paid, balance_due, is_fully_paid) sont annotés avec le
    suffixe _annotated pour éviter l'AttributeError "property has no setter".
    Ils sont renommés vers leurs noms sans suffixe dans la réponse JSON finale.
    """

    # ── Helpers internes ─────────────────────────────────────────────────────

    @staticmethod
    def _parse_iso_any(dt: Optional[str]) -> Optional[datetime]:
        if not dt:
            return None
        try:
            if "T" in dt or " " in dt:
                parsed = parse_datetime(dt)
                if parsed:
                    return make_aware(parsed) if is_naive(parsed) else parsed
            parsed_date = parse_date(dt)
            if parsed_date:
                return make_aware(datetime.combine(parsed_date, time(0, 0, 0)))
        except Exception:
            pass
        return None

    @staticmethod
    def _to_aware(dt_or_d: Optional[object], end_of_day: bool = False) -> Optional[datetime]:
        if dt_or_d is None:
            return None
        tz = get_current_timezone()
        if isinstance(dt_or_d, datetime) and not is_naive(dt_or_d):
            return dt_or_d
        if isinstance(dt_or_d, datetime) and is_naive(dt_or_d):
            return make_aware(dt_or_d, timezone=tz)
        if isinstance(dt_or_d, date) and not isinstance(dt_or_d, datetime):
            dtime = datetime.combine(
                dt_or_d,
                time(23, 59, 59, 999999) if end_of_day else time(0, 0, 0, 0),
            )
            return make_aware(dtime, timezone=tz)
        return dt_or_d

    @staticmethod
    def _normalize_avec_sans(value: Optional[str]) -> Optional[str]:
        if not value:
            return None
        v = value.strip().lower()
        if v in {"avec", "oui", "with", "true", "1"}:
            return "avec"
        if v in {"sans", "non", "without", "false", "0"}:
            return "sans"
        return None

    @staticmethod
    def _to_dec(v: Optional[str]) -> Optional[Decimal]:
        if v is None or v == "":
            return None
        try:
            return Decimal(str(v))
        except Exception:
            return None

    @staticmethod
    def _to_int_or_str(v: Optional[str]) -> Optional[str]:
        if v is None or str(v).strip() == "":
            return None
        return str(v).strip()

    @staticmethod
    def _dec(v: Optional[Decimal]) -> float:
        return float(v or Decimal("0.00"))

    # ── Queryset de base ─────────────────────────────────────────────────────

    @classmethod
    def build_base_queryset(cls):
        """
        Queryset annoté avec tous les champs calculés.

        Les annotations financières utilisent le suffixe _annotated pour ne pas
        entrer en conflit avec les @property sans setter du modèle Contract :
          - amount_paid_annotated   (au lieu de amount_paid)
          - net_paid_annotated      (au lieu de net_paid)
          - balance_due_annotated   (au lieu de balance_due)
          - is_fully_paid_annotated (au lieu de is_fully_paid)
          - next_due_date_annotated (au lieu de next_due_date)
        """
        real_amount_due = ExpressionWrapper(
            F("amount_due") * (
                Value(1.0, output_field=DecimalField())
                - (
                    Coalesce(
                        F("discount_percent"),
                        Value(Decimal("0.00"), output_field=DecimalField()),
                    )
                    / Value(100.0, output_field=DecimalField())
                )
            ),
            output_field=DecimalField(max_digits=12, decimal_places=2),
        )

        amount_paid_annotated = Coalesce(
            Sum(
                "receipts__amount",
                output_field=DecimalField(max_digits=12, decimal_places=2),
            ),
            Value(Decimal("0.00"), output_field=DecimalField()),
        )

        net_paid_annotated = Greatest(
            Value(Decimal("0.00"), output_field=DecimalField()),
            ExpressionWrapper(
                amount_paid_annotated - Coalesce(
                    F("refund_amount"),
                    Value(Decimal("0.00"), output_field=DecimalField()),
                ),
                output_field=DecimalField(max_digits=12, decimal_places=2),
            ),
        )

        balance_due_annotated = Case(
            When(is_cancelled=True, then=Value(Decimal("0.00"), output_field=DecimalField())),
            default=Greatest(
                Value(Decimal("0.00"), output_field=DecimalField()),
                ExpressionWrapper(
                    real_amount_due - net_paid_annotated,
                    output_field=DecimalField(max_digits=12, decimal_places=2),
                ),
            ),
            output_field=DecimalField(max_digits=12, decimal_places=2),
        )

        today = timezone.localdate()

        return (
            Contract.objects
            .select_related("client", "service", "created_by")
            .annotate(
                real_amount_due=real_amount_due,
                amount_paid_annotated=amount_paid_annotated,
                net_paid_annotated=net_paid_annotated,
                balance_due_annotated=balance_due_annotated,
                discount_abs=Coalesce(
                    F("discount_percent"),
                    Value(Decimal("0.00"), output_field=DecimalField()),
                ),
            )
            .annotate(
                is_fully_paid_annotated=Case(
                    When(balance_due_annotated=Decimal("0.00"), then=Value(True)),
                    default=Value(False),
                    output_field=BooleanField(),
                ),
                next_due_date_annotated=Min(
                    "receipts__next_due_date",
                    filter=Q(receipts__next_due_date__gte=today),
                ),
                last_payment_date=Max("receipts__payment_date"),
            )
        )

    # ── Extraction des filtres ────────────────────────────────────────────────

    @classmethod
    def extract_filters_from_request(cls, request):
        raw_date_from = request.query_params.get("date_from")
        raw_date_to   = request.query_params.get("date_to")

        return {
            "date_from":       cls._to_aware(cls._parse_iso_any(raw_date_from), end_of_day=False),
            "date_to":         cls._to_aware(cls._parse_iso_any(raw_date_to),   end_of_day=True),
            "is_signed":       cls._normalize_avec_sans(request.query_params.get("is_signed")),
            "is_refunded":     cls._normalize_avec_sans(request.query_params.get("is_refunded")),
            "is_fully_paid":   cls._normalize_avec_sans(request.query_params.get("is_fully_paid")),
            "has_balance":     cls._normalize_avec_sans(request.query_params.get("has_balance")),
            "with_discount":   cls._normalize_avec_sans(request.query_params.get("with_discount")),
            "is_cancelled":    cls._normalize_avec_sans(request.query_params.get("is_cancelled")),
            "service_id":      cls._to_int_or_str(request.query_params.get("service_id")),
            "service_code":    request.query_params.get("service_code"),
            "client_id":       cls._to_int_or_str(request.query_params.get("client_id")),
            "created_by":      cls._to_int_or_str(request.query_params.get("created_by")),
            "min_amount_due":  cls._to_dec(request.query_params.get("min_amount_due")),
            "max_amount_due":  cls._to_dec(request.query_params.get("max_amount_due")),
            "min_real_amount": cls._to_dec(request.query_params.get("min_real_amount")),
            "max_real_amount": cls._to_dec(request.query_params.get("max_real_amount")),
            "min_balance_due": cls._to_dec(request.query_params.get("min_balance_due")),
            "max_balance_due": cls._to_dec(request.query_params.get("max_balance_due")),
        }

    # ── Application des filtres ───────────────────────────────────────────────

    @classmethod
    def apply_filters(cls, queryset, filters):
        """
        Applique les filtres métiers au queryset.
        Les filtres sur balance_due/is_fully_paid référencent les noms _annotated.
        """
        qs = queryset

        # Dates
        date_from = filters.get("date_from")
        date_to   = filters.get("date_to")
        if date_from and not date_to:
            qs = qs.filter(created_at__date=date_from.date())
        elif date_from:
            qs = qs.filter(created_at__date__gte=date_from.date())
        if date_to:
            qs = qs.filter(created_at__date__lte=date_to.date())

        # Références
        if filters.get("service_id"):
            qs = qs.filter(service_id=filters["service_id"])
        if filters.get("service_code"):
            qs = qs.filter(service__code=filters["service_code"])
        if filters.get("client_id"):
            qs = qs.filter(client_id=filters["client_id"])
        if filters.get("created_by"):
            qs = qs.filter(created_by_id=filters["created_by"])

        # Montants bruts
        if filters.get("min_amount_due") is not None:
            qs = qs.filter(amount_due__gte=filters["min_amount_due"])
        if filters.get("max_amount_due") is not None:
            qs = qs.filter(amount_due__lte=filters["max_amount_due"])
        if filters.get("min_real_amount") is not None:
            qs = qs.filter(real_amount_due__gte=filters["min_real_amount"])
        if filters.get("max_real_amount") is not None:
            qs = qs.filter(real_amount_due__lte=filters["max_real_amount"])

        # 🔥 balance_due_annotated — jamais balance_due (clash @property)
        if filters.get("min_balance_due") is not None:
            qs = qs.filter(balance_due_annotated__gte=filters["min_balance_due"])
        if filters.get("max_balance_due") is not None:
            qs = qs.filter(balance_due_annotated__lte=filters["max_balance_due"])

        # Statuts booléens
        if filters.get("is_cancelled") == "avec":
            qs = qs.filter(is_cancelled=True)
        elif filters.get("is_cancelled") == "sans":
            qs = qs.filter(is_cancelled=False)

        if filters.get("is_signed") == "avec":
            qs = qs.filter(is_signed=True)
        elif filters.get("is_signed") == "sans":
            qs = qs.filter(is_signed=False)

        if filters.get("is_refunded") == "avec":
            qs = qs.filter(is_refunded=True)
        elif filters.get("is_refunded") == "sans":
            qs = qs.filter(is_refunded=False)

        # 🔥 is_fully_paid / has_balance → balance_due_annotated
        if filters.get("is_fully_paid") == "avec":
            qs = qs.filter(balance_due_annotated=Decimal("0.00"))
        elif filters.get("is_fully_paid") == "sans":
            qs = qs.filter(balance_due_annotated__gt=Decimal("0.00"))

        if filters.get("has_balance") == "avec":
            qs = qs.filter(balance_due_annotated__gt=Decimal("0.00"))
        elif filters.get("has_balance") == "sans":
            qs = qs.filter(balance_due_annotated=Decimal("0.00"))

        if filters.get("with_discount") == "avec":
            qs = qs.filter(discount_abs__gt=Decimal("0.00"))
        elif filters.get("with_discount") == "sans":
            qs = qs.filter(discount_abs__lte=Decimal("0.00"))

        return qs

    # ── Agrégats statistiques ─────────────────────────────────────────────────

    @classmethod
    def calculate_aggregates(cls, queryset):
        """Calcule les agrégats financiers et comptages."""

        # Annotation intermédiaire propre (pas de clash avec @property)
        qs_with_payments = queryset.annotate(
            amount_paid_total=Coalesce(
                Sum("receipts__amount"),
                Value(Decimal("0.00")),
                output_field=DecimalField(),
            )
        )

        agg = qs_with_payments.aggregate(
            sum_amount_due=Coalesce(Sum("amount_due"), Value(Decimal("0.00"))),
            sum_real_amount_due=Coalesce(
                Sum(
                    F("amount_due") * (
                        Value(1.0)
                        - (Coalesce(F("discount_percent"), Value(0)) / Value(100.0))
                    ),
                    output_field=DecimalField(max_digits=12, decimal_places=2),
                ),
                Value(Decimal("0.00")),
            ),
            sum_amount_paid=Coalesce(Sum("amount_paid_total"), Value(Decimal("0.00"))),
            sum_net_paid=Coalesce(
                Sum(
                    F("amount_paid_total") - Coalesce(
                        F("refund_amount"), Value(Decimal("0.00"))
                    ),
                    output_field=DecimalField(max_digits=12, decimal_places=2),
                ),
                Value(Decimal("0.00")),
            ),
            count_signed=Count("id", filter=Q(is_signed=True)),
            count_refunded=Count("id", filter=Q(is_refunded=True)),
            count_reduced=Count("id", filter=Q(discount_percent__gt=0)),
            count_cancelled=Count("id", filter=Q(is_cancelled=True)),
        )

        # Balance due — exclure annulés
        balance_agg = (
            qs_with_payments.filter(is_cancelled=False)
            .annotate(
                real_after_discount=ExpressionWrapper(
                    F("amount_due") * (
                        Value(1.0)
                        - (Coalesce(F("discount_percent"), Value(0)) / Value(100.0))
                    ),
                    output_field=DecimalField(max_digits=12, decimal_places=2),
                ),
                net_paid_calc=ExpressionWrapper(
                    F("amount_paid_total") - Coalesce(
                        F("refund_amount"), Value(Decimal("0.00"))
                    ),
                    output_field=DecimalField(max_digits=12, decimal_places=2),
                ),
                balance_calc=ExpressionWrapper(
                    F("real_after_discount") - F("net_paid_calc"),
                    output_field=DecimalField(max_digits=12, decimal_places=2),
                ),
            )
            .aggregate(
                sum_balance_due=Coalesce(
                    Sum(Greatest(Value(Decimal("0.00")), F("balance_calc"))),
                    Value(Decimal("0.00")),
                )
            )
        )

        def _balance_annotated(qs_base):
            return (
                qs_base
                .annotate(
                    real_after_discount=ExpressionWrapper(
                        F("amount_due") * (
                            Value(1.0)
                            - (Coalesce(F("discount_percent"), Value(0)) / Value(100.0))
                        ),
                        output_field=DecimalField(max_digits=12, decimal_places=2),
                    ),
                    net_paid_calc=ExpressionWrapper(
                        F("amount_paid_total") - Coalesce(
                            F("refund_amount"), Value(Decimal("0.00"))
                        ),
                        output_field=DecimalField(max_digits=12, decimal_places=2),
                    ),
                    balance_calc=ExpressionWrapper(
                        F("real_after_discount") - F("net_paid_calc"),
                        output_field=DecimalField(max_digits=12, decimal_places=2),
                    ),
                )
            )

        count_fully_paid = (
            _balance_annotated(qs_with_payments)
            .filter(Q(is_cancelled=True) | Q(balance_calc__lte=Decimal("0.00")))
            .count()
        )

        count_with_balance = (
            _balance_annotated(qs_with_payments)
            .filter(is_cancelled=False, balance_calc__gt=Decimal("0.00"))
            .count()
        )

        return {
            "sum_amount_due":      agg["sum_amount_due"],
            "sum_real_amount_due": agg["sum_real_amount_due"],
            "sum_amount_paid":     agg["sum_amount_paid"],
            "sum_net_paid":        agg["sum_net_paid"],
            "sum_balance_due":     balance_agg["sum_balance_due"],
            "count_signed":        agg["count_signed"],
            "count_refunded":      agg["count_refunded"],
            "count_fully_paid":    count_fully_paid,
            "count_with_balance":  count_with_balance,
            "count_reduced":       agg["count_reduced"],
            "count_cancelled":     agg["count_cancelled"],
        }


# ─────────────────────────────────────────────────────────────────────────────
# ViewSet de recherche
# ─────────────────────────────────────────────────────────────────────────────

class ContractSearchView(ViewSet):
    permission_classes = [IsAuthenticated]

    def list(self, request):
        """Endpoint principal de recherche avec pagination et agrégats."""

        filters = ContractSearchService.extract_filters_from_request(request)

        # Pagination
        try:
            page = max(int(request.query_params.get("page", 1)), 1)
        except Exception:
            page = 1
        try:
            page_size = min(max(int(request.query_params.get("page_size", 20)), 1), 200)
        except Exception:
            page_size = 20

        # Tri — référence les noms _annotated pour les champs calculés
        allowed_ordering = {
            "created_at", "-created_at",
            "amount_due", "-amount_due",
            "real_amount_due", "-real_amount_due",
            "amount_paid_annotated", "-amount_paid_annotated",
            "net_paid_annotated", "-net_paid_annotated",
            "balance_due_annotated", "-balance_due_annotated",
            "id", "-id",
        }
        ordering = request.query_params.get("ordering", "-created_at")
        if ordering not in allowed_ordering:
            ordering = "-created_at"

        # Queryset principal
        qs_base    = ContractSearchService.build_base_queryset()
        qs_display = ContractSearchService.apply_filters(qs_base, filters)

        # Recherche textuelle
        search_query = request.query_params.get("search", "").strip()
        if search_query:
            qs_display = qs_display.filter(
                Q(client__lead__first_name__icontains=search_query) |
                Q(client__lead__last_name__icontains=search_query)  |
                Q(client__lead__email__icontains=search_query)       |
                Q(client__lead__phone__icontains=search_query)       |
                Q(id__icontains=search_query)
            )

        # Agrégats (hors annulés si non demandés explicitement)
        qs_stats = ContractSearchService.build_base_queryset()
        if filters.get("is_cancelled") != "avec":
            qs_stats = qs_stats.filter(is_cancelled=False)
        qs_stats = ContractSearchService.apply_filters(qs_stats, filters)
        agg = ContractSearchService.calculate_aggregates(qs_stats)

        # Pagination
        total = qs_display.count()
        start = (page - 1) * page_size
        end   = start + page_size

        # 🔥 values() utilise les noms _annotated — pas de clash avec les @property
        rows = list(
            qs_display.order_by(ordering).values(
                # Identifiants
                "id",
                "client_id",
                "service_id",
                "created_by_id",
                # Client / Lead
                "client__lead_id",
                "client__lead__first_name",
                "client__lead__last_name",
                "client__lead__email",
                "client__lead__phone",
                # Service
                "service__code",
                "service__label",
                "service__price",
                # Créateur
                "created_by__first_name",
                "created_by__last_name",
                # Montants
                "amount_due",
                "discount_percent",
                "real_amount_due",
                "amount_paid_annotated",
                "net_paid_annotated",
                "balance_due_annotated",
                "refund_amount",
                # Statuts
                "is_fully_paid_annotated",
                "is_signed",
                "is_refunded",
                "is_cancelled",
                # URLs
                "contract_url",
                "invoice_url",
                # Dates
                "created_at",
                "next_due_date_annotated",
                "last_payment_date",
            )[start:end]
        )

        # Renommage _annotated → noms attendus par le frontend
        for row in rows:
            row["amount_paid"]   = row.pop("amount_paid_annotated",   Decimal("0.00"))
            row["net_paid"]      = row.pop("net_paid_annotated",      Decimal("0.00"))
            row["balance_due"]   = row.pop("balance_due_annotated",   Decimal("0.00"))
            row["is_fully_paid"] = row.pop("is_fully_paid_annotated", False)
            row["next_due_date"] = row.pop("next_due_date_annotated", None)

        # Signature des URLs S3
        from urllib.parse import urlparse, unquote
        from api.utils.cloud.scw.bucket_utils import generate_presigned_url

        for row in rows:
            for field, bucket in (("contract_url", "contracts"), ("invoice_url", "invoices")):
                url = row.get(field)
                if url:
                    parsed = urlparse(url)
                    path   = unquote(parsed.path)
                    key    = "/".join(path.strip("/").split("/")[1:])
                    row[field] = generate_presigned_url(bucket, key)

        return Response({
            "total":    total,
            "page":     page,
            "page_size": page_size,
            "ordering": ordering,
            "aggregates": {
                "sum_amount_due":      ContractSearchService._dec(agg["sum_amount_due"]),
                "sum_real_amount_due": ContractSearchService._dec(agg["sum_real_amount_due"]),
                "sum_amount_paid":     ContractSearchService._dec(agg["sum_amount_paid"]),
                "sum_net_paid":        ContractSearchService._dec(agg["sum_net_paid"]),
                "sum_balance_due":     ContractSearchService._dec(agg["sum_balance_due"]),
                "count_signed":        int(agg["count_signed"]        or 0),
                "count_refunded":      int(agg["count_refunded"]      or 0),
                "count_fully_paid":    int(agg["count_fully_paid"]    or 0),
                "count_with_balance":  int(agg["count_with_balance"]  or 0),
                "count_reduced":       int(agg["count_reduced"]       or 0),
                "count_cancelled":     int(agg["count_cancelled"]     or 0),
            },
            "items": rows,
        })

    # ── Export PDF ────────────────────────────────────────────────────────────

    @action(detail=False, methods=["get"], url_path="export-pdf", renderer_classes=[PDFRenderer])
    def export_pdf(self, request):
        filters    = ContractSearchService.extract_filters_from_request(request)
        qs_base    = ContractSearchService.build_base_queryset()
        qs_display = ContractSearchService.apply_filters(qs_base, filters)

        qs_stats = ContractSearchService.build_base_queryset()
        if filters.get("is_cancelled") != "avec":
            qs_stats = qs_stats.filter(is_cancelled=False)
        qs_stats = ContractSearchService.apply_filters(qs_stats, filters)

        # 🔥 Agrégats sur les noms _annotated
        agg = qs_stats.aggregate(
            sum_amount_due=Coalesce(Sum("amount_due"), Value(Decimal("0.00"))),
            sum_real_amount_due=Coalesce(Sum("real_amount_due"), Value(Decimal("0.00"))),
            sum_amount_paid=Coalesce(Sum("amount_paid_annotated"), Value(Decimal("0.00"))),
            sum_net_paid=Coalesce(Sum("net_paid_annotated"), Value(Decimal("0.00"))),
            sum_balance_due=Coalesce(Sum("balance_due_annotated"), Value(Decimal("0.00"))),
            count_signed=Count("id", filter=Q(is_signed=True)),
            count_refunded=Count("id", filter=Q(is_refunded=True)),
            count_fully_paid=Count("id", filter=Q(balance_due_annotated=Decimal("0.00"))),
            count_with_balance=Count("id", filter=Q(balance_due_annotated__gt=Decimal("0.00"))),
            count_reduced=Count("id", filter=Q(discount_abs__gt=Decimal("0.00"))),
            count_cancelled=Count("id", filter=Q(is_cancelled=True)),
        )

        # 🔥 values() avec noms _annotated puis renommage
        rows_raw = list(
            qs_display.order_by("-created_at").values(
                "id",
                "client__lead__first_name",
                "client__lead__last_name",
                "client__lead__email",
                "client__lead__phone",
                "service__label",
                "amount_due",
                "discount_percent",
                "real_amount_due",
                "amount_paid_annotated",
                "net_paid_annotated",
                "balance_due_annotated",
                "is_signed",
                "is_refunded",
                "refund_amount",
                "is_cancelled",
                "created_at",
                "created_by__first_name",
                "created_by__last_name",
            )
        )

        rows = []
        for row in rows_raw:
            row["amount_paid"] = row.pop("amount_paid_annotated", Decimal("0.00"))
            row["net_paid"]    = row.pop("net_paid_annotated",    Decimal("0.00"))
            row["balance_due"] = row.pop("balance_due_annotated", Decimal("0.00"))
            rows.append(row)

        total_count = qs_display.count()
        return self._generate_pdf_response(rows, agg, total_count)

    # ── Export CSV ────────────────────────────────────────────────────────────

    @action(detail=False, methods=["get"], url_path="export-csv")
    def export_csv(self, request):
        import csv

        filters    = ContractSearchService.extract_filters_from_request(request)
        qs_base    = ContractSearchService.build_base_queryset()
        qs_display = ContractSearchService.apply_filters(qs_base, filters)

        # 🔥 values() avec noms _annotated
        rows_raw = list(
            qs_display.order_by("-created_at").values(
                "id",
                "client__lead__first_name",
                "client__lead__last_name",
                "client__lead__email",
                "client__lead__phone",
                "service__label",
                "amount_due",
                "amount_paid_annotated",
                "balance_due_annotated",
                "is_signed",
                "is_cancelled",
                "created_by__first_name",
                "created_by__last_name",
            )
        )

        response = HttpResponse(content_type="text/csv")
        response["Content-Disposition"] = (
            f'attachment; filename="contrats_export_{timezone.now().strftime("%Y%m%d_%H%M%S")}.csv"'
        )

        writer = csv.writer(response)
        writer.writerow([
            "ID Contrat", "Nom Client", "Email", "Téléphone", "Service",
            "Montant Facturé", "Montant Payé", "Solde", "Signé", "Annulé", "Créé par",
        ])

        for row in rows_raw:
            client_name     = f"{row['client__lead__first_name'] or ''} {row['client__lead__last_name'] or ''}".strip()
            created_by_name = f"{row['created_by__first_name'] or ''} {row['created_by__last_name'] or ''}".strip() or "N/A"
            writer.writerow([
                row["id"],
                client_name,
                row["client__lead__email"]  or "N/A",
                row["client__lead__phone"]  or "N/A",
                row["service__label"]       or "N/A",
                f"{_dec(row['amount_due']):.2f}",
                f"{_dec(row['amount_paid_annotated']):.2f}",
                f"{_dec(row['balance_due_annotated']):.2f}",
                "Oui" if row["is_signed"]    else "Non",
                "Oui" if row["is_cancelled"] else "Non",
                created_by_name,
            ])

        return response

    # ── Générateur PDF ────────────────────────────────────────────────────────

    def _generate_pdf_response(self, rows, aggregates, total_count):
        buffer = BytesIO()
        doc = SimpleDocTemplate(
            buffer,
            pagesize=landscape(A4),
            rightMargin=1 * cm, leftMargin=1 * cm,
            topMargin=1.5 * cm, bottomMargin=1.5 * cm,
        )

        elements = []
        styles   = getSampleStyleSheet()

        title_style = ParagraphStyle(
            "CustomTitle",
            parent=styles["Heading1"],
            fontSize=18,
            textColor=colors.HexColor("#1a1a1a"),
            spaceAfter=20,
            alignment=1,
        )

        elements.append(Paragraph("Rapport des Contrats", title_style))
        elements.append(Paragraph(
            f"<b>Généré le :</b> {timezone.now().strftime('%d/%m/%Y à %H:%M')}",
            styles["Normal"],
        ))
        elements.append(Spacer(1, 0.5 * cm))

        # Statistiques
        elements.append(Paragraph("<b>Statistiques Globales</b>", styles["Heading2"]))
        elements.append(Spacer(1, 0.3 * cm))

        stats_data = [
            ["Indicateur", "Valeur"],
            ["Nombre total de contrats",    str(total_count)],
            ["Montant total dû",            f"{ContractSearchService._dec(aggregates['sum_amount_due']):.2f} €"],
            ["Montant réel (après remise)", f"{ContractSearchService._dec(aggregates['sum_real_amount_due']):.2f} €"],
            ["Total payé",                  f"{ContractSearchService._dec(aggregates['sum_amount_paid']):.2f} €"],
            ["Total net payé",              f"{ContractSearchService._dec(aggregates['sum_net_paid']):.2f} €"],
            ["Solde restant dû",            f"{ContractSearchService._dec(aggregates['sum_balance_due']):.2f} €"],
            ["Contrats signés",             f"{aggregates['count_signed']}"],
            ["Contrats remboursés",         f"{aggregates['count_refunded']}"],
            ["Contrats soldés",             f"{aggregates['count_fully_paid']}"],
            ["Contrats avec solde",         f"{aggregates['count_with_balance']}"],
            ["Contrats avec remise",        f"{aggregates['count_reduced']}"],
            ["Contrats annulés",            f"{aggregates['count_cancelled']}"],
        ]

        stats_table = Table(stats_data, colWidths=[10 * cm, 8 * cm])
        stats_table.setStyle(TableStyle([
            ("BACKGROUND",     (0, 0), (-1, 0),  colors.HexColor("#2c3e50")),
            ("TEXTCOLOR",      (0, 0), (-1, 0),  colors.whitesmoke),
            ("ALIGN",          (0, 0), (-1, -1), "LEFT"),
            ("ALIGN",          (1, 1), (1, -1),  "RIGHT"),
            ("FONTNAME",       (0, 0), (-1, 0),  "Helvetica-Bold"),
            ("FONTSIZE",       (0, 0), (-1, 0),  10),
            ("BOTTOMPADDING",  (0, 0), (-1, 0),  12),
            ("BACKGROUND",     (0, 1), (-1, -1), colors.beige),
            ("GRID",           (0, 0), (-1, -1), 1, colors.black),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.lightgrey]),
        ]))
        elements.append(stats_table)
        elements.append(PageBreak())

        # Détails
        elements.append(Paragraph("<b>Détails des Contrats</b>", styles["Heading2"]))
        elements.append(Spacer(1, 0.3 * cm))

        contract_data = [[
            "ID", "Client", "Email", "Téléphone", "Service",
            "Montant", "Payé", "Solde", "Signé", "Annulé", "Créé par",
        ]]

        for row in rows:
            client_name = (
                f"{row['client__lead__first_name'] or ''} "
                f"{row['client__lead__last_name'] or ''}"
            ).strip()
            created_by_name = (
                f"{row['created_by__first_name'] or ''} "
                f"{row['created_by__last_name'] or ''}"
            ).strip() or "N/A"

            contract_data.append([
                str(row["id"]),
                client_name,
                row["client__lead__email"] or "N/A",
                row["client__lead__phone"] or "N/A",
                row["service__label"]      or "N/A",
                f"{ContractSearchService._dec(row['amount_due']):.2f} €",
                f"{ContractSearchService._dec(row['amount_paid']):.2f} €",
                f"{ContractSearchService._dec(row['balance_due']):.2f} €",
                "✓" if row["is_signed"]    else "✗",
                "✓" if row["is_cancelled"] else "✗",
                created_by_name,
            ])

        col_widths = [
            1.5*cm, 3*cm, 3.5*cm, 2.5*cm, 4*cm,
            2*cm, 2*cm, 2*cm, 1.2*cm, 1.2*cm, 2.5*cm,
        ]

        contract_table = Table(contract_data, colWidths=col_widths, repeatRows=1)
        contract_table.setStyle(TableStyle([
            ("BACKGROUND",     (0, 0), (-1, 0),  colors.HexColor("#34495e")),
            ("TEXTCOLOR",      (0, 0), (-1, 0),  colors.whitesmoke),
            ("ALIGN",          (0, 0), (-1, -1), "CENTER"),
            ("FONTNAME",       (0, 0), (-1, 0),  "Helvetica-Bold"),
            ("FONTSIZE",       (0, 0), (-1, 0),  7),
            ("FONTSIZE",       (0, 1), (-1, -1), 6),
            ("BOTTOMPADDING",  (0, 0), (-1, 0),  6),
            ("TOPPADDING",     (0, 1), (-1, -1), 3),
            ("BOTTOMPADDING",  (0, 1), (-1, -1), 3),
            ("GRID",           (0, 0), (-1, -1), 0.5, colors.grey),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f8f9fa")]),
            ("WORDWRAP",       (0, 0), (-1, -1), True),
        ]))
        elements.append(contract_table)

        doc.build(elements)
        buffer.seek(0)

        response = HttpResponse(buffer.getvalue(), content_type="application/pdf")
        filename = f"contrats_export_{timezone.now().strftime('%Y%m%d_%H%M%S')}.pdf"
        response["Content-Disposition"] = f'attachment; filename="{filename}"'
        return response