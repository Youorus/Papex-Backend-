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


# Additional top-level helpers for PDF export
def _to_dec(v):
    return ContractSearchService._to_dec(v)


def _to_int_or_str(v):
    return ContractSearchService._to_int_or_str(v)


def _to_aware(
        dt_or_d: Optional[object], end_of_day: bool = False
) -> Optional[datetime]:
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


class ContractSearchService:
    """Service pour gérer la recherche et le filtrage des contrats"""

    @staticmethod
    def _parse_iso_any(dt: Optional[str]) -> Optional[datetime]:
        """Parse une date ISO en datetime aware"""
        if not dt:
            return None

        try:
            # Essayer le format datetime complet
            if 'T' in dt or ' ' in dt:
                parsed = parse_datetime(dt)
                if parsed:
                    return make_aware(parsed) if is_naive(parsed) else parsed

            # Essayer le format date simple (YYYY-MM-DD)
            parsed_date = parse_date(dt)
            if parsed_date:
                # Retourner un datetime à minuit pour la date
                return make_aware(datetime.combine(parsed_date, time(0, 0, 0)))

        except Exception as e:
            print(f"Erreur parsing date {dt}: {e}")

        return None

    @staticmethod
    def _to_aware(dt_or_d: Optional[object], end_of_day: bool = False) -> Optional[datetime]:
        """Convertit en datetime aware"""
        if dt_or_d is None:
            return None

        tz = get_current_timezone()

        # Si c'est déjà un datetime aware, le retourner tel quel
        if isinstance(dt_or_d, datetime) and not is_naive(dt_or_d):
            return dt_or_d

        # Si c'est un datetime naïf, le rendre aware
        if isinstance(dt_or_d, datetime) and is_naive(dt_or_d):
            return make_aware(dt_or_d, timezone=tz)

        # Si c'est une date, la convertir en datetime
        if isinstance(dt_or_d, date) and not isinstance(dt_or_d, datetime):
            if end_of_day:
                dtime = datetime.combine(dt_or_d, time(23, 59, 59, 999999))
            else:
                dtime = datetime.combine(dt_or_d, time(0, 0, 0, 0))
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

    @classmethod
    def build_base_queryset(cls):
        """Construit le queryset de base avec les annotations communes"""
        # CORRECTION : Définir explicitement output_field pour toutes les expressions
        real_amount_due = ExpressionWrapper(
            F("amount_due")
            * (
                    Value(1.0, output_field=DecimalField())
                    - (
                            Coalesce(F("discount_percent"), Value(Decimal("0.00"), output_field=DecimalField()))
                            / Value(100.0, output_field=DecimalField())
                    )
            ),
            output_field=DecimalField(max_digits=12, decimal_places=2),
        )

        amount_paid = Coalesce(
            Sum("receipts__amount", output_field=DecimalField(max_digits=12, decimal_places=2)),
            Value(Decimal("0.00"), output_field=DecimalField())
        )

        net_paid = Greatest(
            Value(Decimal("0.00"), output_field=DecimalField()),
            ExpressionWrapper(
                amount_paid - Coalesce(F("refund_amount"), Value(Decimal("0.00"), output_field=DecimalField())),
                output_field=DecimalField(max_digits=12, decimal_places=2),
            ),
        )

        # CORRECTION : Pour les contrats annulés, le balance_due est 0
        balance_due = Case(
            When(is_cancelled=True, then=Value(Decimal("0.00"), output_field=DecimalField())),
            # Contrats annulés = solde 0
            default=Greatest(
                Value(Decimal("0.00"), output_field=DecimalField()),
                ExpressionWrapper(
                    real_amount_due - net_paid,
                    output_field=DecimalField(max_digits=12, decimal_places=2),
                ),
            ),
            output_field=DecimalField(max_digits=12, decimal_places=2),
        )

        today = timezone.localdate()

        qs_base = Contract.objects.select_related("client", "service", "created_by")

        return qs_base.annotate(
            real_amount_due=real_amount_due,
            amount_paid=amount_paid,
            net_paid=net_paid,
            balance_due=balance_due,  # Utilise la version corrigée
            discount_abs=Coalesce(F("discount_percent"), Value(Decimal("0.00"), output_field=DecimalField())),
        ).annotate(
            is_fully_paid=Case(
                When(balance_due=Decimal("0.00"), then=Value(True)),
                default=Value(False),
                output_field=BooleanField(),
            ),
            next_due_date=Min(
                "receipts__next_due_date",
                filter=Q(receipts__next_due_date__gte=today),
            ),
            last_payment_date=Max("receipts__payment_date"),
        )

    @classmethod
    def apply_filters(cls, queryset, filters):
        """Applique les filtres au queryset"""
        qs = queryset

        # DEBUG: Afficher les dates reçues
        print(f"DEBUG - date_from: {filters.get('date_from')}, type: {type(filters.get('date_from'))}")
        print(f"DEBUG - date_to: {filters.get('date_to')}, type: {type(filters.get('date_to'))}")

        # Filtres de date
        date_from = filters.get('date_from')
        date_to = filters.get('date_to')

        if date_from and not date_to:
            print(f"DEBUG - Filtrage date EXACT (DATE ONLY): {date_from}")
            qs = qs.filter(created_at__date=date_from.date())
            print(f"DEBUG - Après filtre date_exact, count: {qs.count()}")

        elif date_from:
            print(f"DEBUG - Filtrage date_from (DATE ONLY): {date_from}")
            qs = qs.filter(created_at__date__gte=date_from.date())
            print(f"DEBUG - Après filtre date_from (date__gte), count: {qs.count()}")

        if date_to:
            print(f"DEBUG - Filtrage date_to (DATE ONLY): {date_to}")
            qs = qs.filter(created_at__date__lte=date_to.date())
            print(f"DEBUG - Après filtre date_to (date__lte), count: {qs.count()}")

        # Filtres simples
        if filters.get('service_id'):
            qs = qs.filter(service_id=filters['service_id'])
        if filters.get('service_code'):
            qs = qs.filter(service__code=filters['service_code'])
        if filters.get('client_id'):
            qs = qs.filter(client_id=filters['client_id'])
        if filters.get('created_by'):
            qs = qs.filter(created_by_id=filters['created_by'])

        # Filtres de montant
        if filters.get('min_amount_due') is not None:
            qs = qs.filter(amount_due__gte=filters['min_amount_due'])
        if filters.get('max_amount_due') is not None:
            qs = qs.filter(amount_due__lte=filters['max_amount_due'])
        if filters.get('min_real_amount') is not None:
            qs = qs.filter(real_amount_due__gte=filters['min_real_amount'])
        if filters.get('max_real_amount') is not None:
            qs = qs.filter(real_amount_due__lte=filters['max_real_amount'])
        if filters.get('min_balance_due') is not None:
            qs = qs.filter(balance_due__gte=filters['min_balance_due'])
        if filters.get('max_balance_due') is not None:
            qs = qs.filter(balance_due__lte=filters['max_balance_due'])

        # Filtres booléens
        if filters.get('is_cancelled') == "avec":
            qs = qs.filter(is_cancelled=True)
        elif filters.get('is_cancelled') == "sans":
            qs = qs.filter(is_cancelled=False)

        if filters.get('is_signed') == "avec":
            qs = qs.filter(is_signed=True)
        elif filters.get('is_signed') == "sans":
            qs = qs.filter(is_signed=False)

        if filters.get('is_refunded') == "avec":
            qs = qs.filter(is_refunded=True)
        elif filters.get('is_refunded') == "sans":
            qs = qs.filter(is_refunded=False)

        if filters.get('fully_paid') == "avec":
            qs = qs.filter(balance_due=Decimal("0.00"))
        elif filters.get('fully_paid') == "sans":
            qs = qs.filter(balance_due__gt=Decimal("0.00"))

        if filters.get('has_balance') == "avec":
            qs = qs.filter(balance_due__gt=Decimal("0.00"))
        elif filters.get('has_balance') == "sans":
            qs = qs.filter(balance_due=Decimal("0.00"))

        if filters.get('with_discount') == "avec":
            qs = qs.filter(discount_abs__gt=Decimal("0.00"))
        elif filters.get('with_discount') == "sans":
            qs = qs.filter(discount_abs__lte=Decimal("0.00"))

        return qs

    @classmethod
    def extract_filters_from_request(cls, request):
        """Extrait et normalise les filtres depuis la requête"""
        raw_date_from = request.query_params.get("date_from")
        raw_date_to = request.query_params.get("date_to")

        return {
            'date_from': cls._to_aware(cls._parse_iso_any(raw_date_from), end_of_day=False),
            'date_to': cls._to_aware(cls._parse_iso_any(raw_date_to), end_of_day=True),
            'is_signed': cls._normalize_avec_sans(request.query_params.get("is_signed")),
            'is_refunded': cls._normalize_avec_sans(request.query_params.get("is_refunded")),
            'fully_paid': cls._normalize_avec_sans(request.query_params.get("is_fully_paid")),
            'has_balance': cls._normalize_avec_sans(request.query_params.get("has_balance")),
            'with_discount': cls._normalize_avec_sans(request.query_params.get("with_discount")),
            'is_cancelled': cls._normalize_avec_sans(request.query_params.get("is_cancelled")),
            'service_id': cls._to_int_or_str(request.query_params.get("service_id")),
            'service_code': request.query_params.get("service_code"),
            'client_id': cls._to_int_or_str(request.query_params.get("client_id")),
            'created_by': cls._to_int_or_str(request.query_params.get("created_by")),
            'min_amount_due': cls._to_dec(request.query_params.get("min_amount_due")),
            'max_amount_due': cls._to_dec(request.query_params.get("max_amount_due")),
            'min_real_amount': cls._to_dec(request.query_params.get("min_real_amount")),
            'max_real_amount': cls._to_dec(request.query_params.get("max_real_amount")),
            'min_balance_due': cls._to_dec(request.query_params.get("min_balance_due")),
            'max_balance_due': cls._to_dec(request.query_params.get("max_balance_due")),
        }

    @classmethod
    def calculate_aggregates(cls, queryset):
        """Calcule les agrégats statistiques - Version CORRIGÉE"""

        # ✅ Annoter amount_paid_total AVANT d'agréger
        qs_with_payments = queryset.annotate(
            amount_paid_total=Coalesce(
                Sum("receipts__amount"),
                Value(Decimal("0.00")),
                output_field=DecimalField()
            )
        )

        # Agrégats principaux
        agg = qs_with_payments.aggregate(
            sum_amount_due=Coalesce(
                Sum("amount_due"),
                Value(Decimal("0.00"))
            ),

            # Montant réel après remise
            sum_real_amount_due=Coalesce(
                Sum(
                    F("amount_due") * (
                            Value(1.0) - (
                            Coalesce(F("discount_percent"), Value(0)) / Value(100.0)
                    )
                    ),
                    output_field=DecimalField(max_digits=12, decimal_places=2)
                ),
                Value(Decimal("0.00"))
            ),

            # ✅ Total payé (somme des receipts)
            sum_amount_paid=Coalesce(
                Sum("amount_paid_total"),
                Value(Decimal("0.00"))
            ),

            # ✅ Net payé = payé - remboursements
            sum_net_paid=Coalesce(
                Sum(
                    F("amount_paid_total") - Coalesce(F("refund_amount"), Value(Decimal("0.00"))),
                    output_field=DecimalField(max_digits=12, decimal_places=2)
                ),
                Value(Decimal("0.00"))
            ),

            # Comptages
            count_signed=Count("id", filter=Q(is_signed=True)),
            count_refunded=Count("id", filter=Q(is_refunded=True)),
            count_reduced=Count("id", filter=Q(discount_percent__gt=0)),
            count_cancelled=Count("id", filter=Q(is_cancelled=True)),
        )

        # ✅ Balance due : EXCLURE les annulés ET calculer correctement
        balance_agg = qs_with_payments.filter(
            is_cancelled=False
        ).annotate(
            real_after_discount=ExpressionWrapper(
                F("amount_due") * (
                        Value(1.0) - (
                        Coalesce(F("discount_percent"), Value(0)) / Value(100.0)
                )
                ),
                output_field=DecimalField(max_digits=12, decimal_places=2)
            ),
            net_paid_calc=ExpressionWrapper(
                F("amount_paid_total") - Coalesce(F("refund_amount"), Value(Decimal("0.00"))),
                output_field=DecimalField(max_digits=12, decimal_places=2)
            ),
            balance_calc=ExpressionWrapper(
                F("real_after_discount") - F("net_paid_calc"),
                output_field=DecimalField(max_digits=12, decimal_places=2)
            )
        ).aggregate(
            sum_balance_due=Coalesce(
                Sum(
                    Greatest(
                        Value(Decimal("0.00")),
                        F("balance_calc")
                    )
                ),
                Value(Decimal("0.00"))
            )
        )

        # ✅ Fully paid : annulés OU balance = 0
        count_fully_paid = qs_with_payments.annotate(
            real_after_discount=ExpressionWrapper(
                F("amount_due") * (
                        Value(1.0) - (
                        Coalesce(F("discount_percent"), Value(0)) / Value(100.0)
                )
                ),
                output_field=DecimalField(max_digits=12, decimal_places=2)
            ),
            net_paid_calc=ExpressionWrapper(
                F("amount_paid_total") - Coalesce(F("refund_amount"), Value(Decimal("0.00"))),
                output_field=DecimalField(max_digits=12, decimal_places=2)
            ),
            balance_calc=ExpressionWrapper(
                F("real_after_discount") - F("net_paid_calc"),
                output_field=DecimalField(max_digits=12, decimal_places=2)
            )
        ).filter(
            Q(is_cancelled=True) | Q(balance_calc__lte=Decimal("0.00"))
        ).count()

        # ✅ With balance : NON annulés ET balance > 0
        count_with_balance = qs_with_payments.filter(
            is_cancelled=False
        ).annotate(
            real_after_discount=ExpressionWrapper(
                F("amount_due") * (
                        Value(1.0) - (
                        Coalesce(F("discount_percent"), Value(0)) / Value(100.0)
                )
                ),
                output_field=DecimalField(max_digits=12, decimal_places=2)
            ),
            net_paid_calc=ExpressionWrapper(
                F("amount_paid_total") - Coalesce(F("refund_amount"), Value(Decimal("0.00"))),
                output_field=DecimalField(max_digits=12, decimal_places=2)
            ),
            balance_calc=ExpressionWrapper(
                F("real_after_discount") - F("net_paid_calc"),
                output_field=DecimalField(max_digits=12, decimal_places=2)
            )
        ).filter(
            balance_calc__gt=Decimal("0.00")
        ).count()

        return {
            'sum_amount_due': agg['sum_amount_due'],
            'sum_real_amount_due': agg['sum_real_amount_due'],
            'sum_amount_paid': agg['sum_amount_paid'],
            'sum_net_paid': agg['sum_net_paid'],
            'sum_balance_due': balance_agg['sum_balance_due'],
            'count_signed': agg['count_signed'],
            'count_refunded': agg['count_refunded'],
            'count_fully_paid': count_fully_paid,
            'count_with_balance': count_with_balance,
            'count_reduced': agg['count_reduced'],
            'count_cancelled': agg['count_cancelled'],
        }


class ContractSearchView(ViewSet):
    permission_classes = [IsAuthenticated]

    def list(self, request):
        """Endpoint principal de recherche avec pagination"""
        # Extraction des paramètres
        filters = ContractSearchService.extract_filters_from_request(request)

        # Gestion de la pagination
        try:
            page = max(int(request.query_params.get("page", 1)), 1)
        except Exception:
            page = 1
        try:
            page_size = min(max(int(request.query_params.get("page_size", 20)), 1), 200)
        except Exception:
            page_size = 20

        # Gestion du tri
        allowed_ordering = {
            "created_at", "-created_at", "amount_due", "-amount_due",
            "real_amount_due", "-real_amount_due", "amount_paid", "-amount_paid",
            "net_paid", "-net_paid", "balance_due", "-balance_due", "id", "-id",
        }
        ordering = request.query_params.get("ordering", "-created_at")
        if ordering not in allowed_ordering:
            ordering = "-created_at"

        # Construction du queryset
        qs_base = ContractSearchService.build_base_queryset()
        qs_display = ContractSearchService.apply_filters(qs_base, filters)

        # Calcul des statistiques
        qs_stats = qs_base
        if filters.get('is_cancelled') != "avec":  # Si on ne demande pas explicitement les annulés
            qs_stats = qs_stats.filter(is_cancelled=False)  # On les exclut des stats

        qs_stats = ContractSearchService.apply_filters(qs_stats, filters)

        # Agrégats
        agg = ContractSearchService.calculate_aggregates(qs_stats)

        # Pagination
        total = qs_display.count()
        qs_display = qs_display.order_by(ordering)
        start = (page - 1) * page_size
        end = start + page_size

        # Récupération des données
        rows = list(
            qs_display.values(
                "id",
                "client_id",
                "service_id",
                "created_by_id",
                "client__lead__first_name",
                "client__lead__last_name",
                "client__lead__email",
                "client__lead__phone",
                "service__code",
                "service__label",
                "service__price",
                "created_by__first_name",
                "created_by__last_name",
                "amount_due",
                "discount_percent",
                "real_amount_due",
                "amount_paid",
                "net_paid",
                "balance_due",
                "is_fully_paid",
                "is_refunded",
                "refund_amount",
                "is_signed",
                "contract_url",
                "invoice_url",
                "created_at",
                "next_due_date",
                "last_payment_date",
                "is_cancelled",
            )[start:end]
        )

        # Sign URLs for contract and invoice
        from urllib.parse import urlparse, unquote
        from api.utils.cloud.scw.bucket_utils import generate_presigned_url

        for row in rows:
            # Sign contract_url
            contract_url = row.get("contract_url")
            if contract_url:
                parsed = urlparse(contract_url)
                path = unquote(parsed.path)
                key = "/".join(path.strip("/").split("/")[1:])
                row["contract_url"] = generate_presigned_url("contracts", key)

            # Sign invoice_url
            invoice_url = row.get("invoice_url")
            if invoice_url:
                parsed = urlparse(invoice_url)
                path = unquote(parsed.path)
                key = "/".join(path.strip("/").split("/")[1:])
                row["invoice_url"] = generate_presigned_url("invoices", key)

        return Response({
            "total": total,
            "page": page,
            "page_size": page_size,
            "ordering": ordering,
            "aggregates": {
                "sum_amount_due": ContractSearchService._dec(agg["sum_amount_due"]),
                "sum_real_amount_due": ContractSearchService._dec(agg["sum_real_amount_due"]),
                "sum_amount_paid": ContractSearchService._dec(agg["sum_amount_paid"]),
                "sum_net_paid": ContractSearchService._dec(agg["sum_net_paid"]),
                "sum_balance_due": ContractSearchService._dec(agg["sum_balance_due"]),  # Maintenant correct
                "count_signed": int(agg["count_signed"] or 0),
                "count_refunded": int(agg["count_refunded"] or 0),
                "count_fully_paid": int(agg["count_fully_paid"] or 0),
                "count_with_balance": int(agg["count_with_balance"] or 0),
                "count_reduced": int(agg["count_reduced"] or 0),
                "count_cancelled": int(agg["count_cancelled"] or 0),
            },
            "items": rows,
        })

    @action(detail=False, methods=["get"], url_path="export-pdf", renderer_classes=[PDFRenderer])
    def export_pdf(self, request):
        """
        Génère un PDF récapitulatif des contrats selon les filtres appliqués.
        Utilise les mêmes paramètres que la recherche normale.
        """
        # ============================================
        # RÉCUPÉRATION DES PARAMÈTRES (même logique que get())
        # ============================================
        raw_date_from = request.query_params.get("date_from")
        raw_date_to = request.query_params.get("date_to")

        is_signed_param = _normalize_avec_sans(request.query_params.get("is_signed"))
        is_refunded_param = _normalize_avec_sans(request.query_params.get("is_refunded"))
        fully_paid_param = _normalize_avec_sans(request.query_params.get("is_fully_paid"))
        has_balance_param = _normalize_avec_sans(request.query_params.get("has_balance"))
        with_discount = _normalize_avec_sans(request.query_params.get("with_discount"))
        is_cancelled_param = _normalize_avec_sans(request.query_params.get("is_cancelled"))

        service_id = _to_int_or_str(request.query_params.get("service_id"))
        service_code = request.query_params.get("service_code")
        client_id = _to_int_or_str(request.query_params.get("client_id"))
        created_by = _to_int_or_str(request.query_params.get("created_by"))

        min_amount_due = _to_dec(request.query_params.get("min_amount_due"))
        max_amount_due = _to_dec(request.query_params.get("max_amount_due"))
        min_real_amount = _to_dec(request.query_params.get("min_real_amount"))
        max_real_amount = _to_dec(request.query_params.get("max_real_amount"))
        min_balance_due = _to_dec(request.query_params.get("min_balance_due"))
        max_balance_due = _to_dec(request.query_params.get("max_balance_due"))

        date_from = _to_aware(_parse_iso_any(raw_date_from), end_of_day=False)
        date_to = _to_aware(_parse_iso_any(raw_date_to), end_of_day=True)

        # ============================================
        # CONSTRUCTION DU QUERYSET (UTILISE EXACTEMENT LA MÊME LOGIQUE QUE list())
        # ============================================

        # On réutilise la logique centralisée
        qs_base = ContractSearchService.build_base_queryset()

        # On applique les mêmes filtres que pour la recherche normale
        filters = ContractSearchService.extract_filters_from_request(request)
        qs_display = ContractSearchService.apply_filters(qs_base, filters)

        # Stats : même logique que list()
        if filters.get('is_cancelled') != "avec":
            qs_stats = qs_base.filter(is_cancelled=False)
        else:
            qs_stats = qs_base.filter(is_cancelled=True)

        qs_stats = ContractSearchService.apply_filters(qs_stats, filters)

        # Agrégats
        agg = qs_stats.aggregate(
            sum_amount_due=Coalesce(Sum("amount_due"), Value(Decimal("0.00"))),
            sum_real_amount_due=Coalesce(Sum("real_amount_due"), Value(Decimal("0.00"))),
            sum_amount_paid=Coalesce(Sum("amount_paid"), Value(Decimal("0.00"))),
            sum_net_paid=Coalesce(Sum("net_paid"), Value(Decimal("0.00"))),
            sum_balance_due=Coalesce(Sum("balance_due"), Value(Decimal("0.00"))),
            count_signed=Count("id", filter=Q(is_signed=True)),
            count_refunded=Count("id", filter=Q(is_refunded=True)),
            count_fully_paid=Count("id", filter=Q(balance_due=Decimal("0.00"))),
            count_with_balance=Count("id", filter=Q(balance_due__gt=Decimal("0.00"))),
            count_reduced=Count("id", filter=Q(discount_abs__gt=Decimal("0.00"))),
            count_cancelled=Count("id", filter=Q(is_cancelled=True)),
        )

        # Récupération des données avec tous les champs nécessaires
        rows = list(
            qs_display.values(
                "id",
                "client__lead__first_name",
                "client__lead__last_name",
                "client__lead__email",  # Ajouté
                "client__lead__phone",  # Ajouté
                "service__label",
                "amount_due",
                "discount_percent",
                "real_amount_due",
                "amount_paid",
                "net_paid",
                "balance_due",
                "is_signed",
                "is_refunded",
                "refund_amount",
                "is_cancelled",
                "created_at",
                "created_by__first_name",  # Ajouté
                "created_by__last_name",  # Ajouté
            ).order_by("-created_at")
        )

        # ============================================
        # GÉNÉRATION DU PDF
        # ============================================
        buffer = BytesIO()
        doc = SimpleDocTemplate(
            buffer,
            pagesize=landscape(A4),
            rightMargin=1 * cm,
            leftMargin=1 * cm,
            topMargin=1.5 * cm,
            bottomMargin=1.5 * cm,
        )

        elements = []
        styles = getSampleStyleSheet()

        # Style personnalisé pour le titre
        title_style = ParagraphStyle(
            'CustomTitle',
            parent=styles['Heading1'],
            fontSize=18,
            textColor=colors.HexColor('#1a1a1a'),
            spaceAfter=20,
            alignment=1,  # Centré
        )

        # Titre
        title = Paragraph("Rapport des Contrats - TDS France", title_style)
        elements.append(title)

        # Date de génération
        date_generation = Paragraph(
            f"<b>Généré le :</b> {timezone.now().strftime('%d/%m/%Y à %H:%M')}",
            styles['Normal']
        )
        elements.append(date_generation)
        elements.append(Spacer(1, 0.5 * cm))

        # ============================================
        # SECTION STATISTIQUES
        # ============================================
        stats_title = Paragraph("<b>Statistiques Globales</b>", styles['Heading2'])
        elements.append(stats_title)
        elements.append(Spacer(1, 0.3 * cm))

        stats_data = [
            ['Indicateur', 'Valeur'],
            ['Nombre total de contrats', str(qs_display.count())],
            ['Montant total dû', f"{_dec(agg['sum_amount_due']):.2f} €"],
            ['Montant réel (après remise)', f"{_dec(agg['sum_real_amount_due']):.2f} €"],
            ['Total payé', f"{_dec(agg['sum_amount_paid']):.2f} €"],
            ['Total net payé', f"{_dec(agg['sum_net_paid']):.2f} €"],
            ['Solde restant dû', f"{_dec(agg['sum_balance_due']):.2f} €"],
            ['Contrats signés', f"{agg['count_signed']}"],
            ['Contrats remboursés', f"{agg['count_refunded']}"],
            ['Contrats soldés', f"{agg['count_fully_paid']}"],
            ['Contrats avec solde', f"{agg['count_with_balance']}"],
            ['Contrats avec remise', f"{agg['count_reduced']}"],
            ['Contrats annulés', f"{agg['count_cancelled']}"],
        ]

        stats_table = Table(stats_data, colWidths=[10 * cm, 8 * cm])
        stats_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#2c3e50')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('ALIGN', (1, 1), (1, -1), 'RIGHT'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 10),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
            ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
            ('GRID', (0, 0), (-1, -1), 1, colors.black),
            ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.lightgrey]),
        ]))

        elements.append(stats_table)
        elements.append(PageBreak())

        # ============================================
        # SECTION DÉTAILS DES CONTRATS
        # ============================================
        details_title = Paragraph("<b>Détails des Contrats</b>", styles['Heading2'])
        elements.append(details_title)
        elements.append(Spacer(1, 0.3 * cm))

        # En-têtes du tableau avec toutes les colonnes demandées
        contract_data = [
            [
                'ID Contrat',
                'Nom Client',
                'Email',
                'Téléphone',
                'Service',
                'Montant Service',
                'Montant Payé',
                'Solde',
                'Signé',
                'Annulé',
                'Créé par'
            ]
        ]

        # Données des contrats avec toutes les informations
        for row in rows:
            client_name = f"{row['client__lead__first_name'] or ''} {row['client__lead__last_name'] or ''}".strip()
            email = row['client__lead__email'] or 'N/A'
            phone = row['client__lead__phone'] or 'N/A'
            service_label = row['service__label'] or 'N/A'
            created_by_name = f"{row['created_by__first_name'] or ''} {row['created_by__last_name'] or ''}".strip() or 'N/A'

            contract_data.append([
                str(row['id']),
                client_name,
                email,
                phone,
                service_label,  # Service complet, non coupé
                f"{_dec(row['amount_due']):.2f} €",
                f"{_dec(row['amount_paid']):.2f} €",
                f"{_dec(row['balance_due']):.2f} €",
                '✓' if row['is_signed'] else '✗',
                '✓' if row['is_cancelled'] else '✗',
                created_by_name
            ])

        # Largeurs des colonnes optimisées pour paysage A4 avec les nouvelles colonnes
        col_widths = [
            2 * cm,  # ID Contrat
            3 * cm,  # Nom Client
            3.5 * cm,  # Email
            2.5 * cm,  # Téléphone
            4 * cm,  # Service (plus large pour le nom complet)
            2 * cm,  # Montant Service
            2 * cm,  # Montant Payé
            2 * cm,  # Solde
            1.5 * cm,  # Signé
            1.5 * cm,  # Annulé
            2.5 * cm  # Créé par
        ]

        contract_table = Table(contract_data, colWidths=col_widths, repeatRows=1)
        contract_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#34495e')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 7),  # Taille réduite pour accommoder plus de colonnes
            ('FONTSIZE', (0, 1), (-1, -1), 6),  # Taille réduite pour les données
            ('BOTTOMPADDING', (0, 0), (-1, 0), 6),
            ('TOPPADDING', (0, 1), (-1, -1), 3),
            ('BOTTOMPADDING', (0, 1), (-1, -1), 3),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
            ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#f8f9fa')]),
            # Permettre le retour à la ligne pour les cellules longues
            ('WORDWRAP', (0, 0), (-1, -1), True),
        ]))

        elements.append(contract_table)

        # Construction du PDF
        doc.build(elements)
        buffer.seek(0)

        # Réponse HTTP
        response = HttpResponse(buffer.getvalue(), content_type='application/pdf')
        filename = f"contrats_export_{timezone.now().strftime('%Y%m%d_%H%M%S')}.pdf"
        response['Content-Disposition'] = f'attachment; filename="{filename}"'

        return response

    @action(detail=False, methods=["get"], url_path="export-csv")
    def export_csv(self, request):
        """Export CSV avec toutes les colonnes demandées"""
        # Même logique de filtrage que pour le PDF
        filters = ContractSearchService.extract_filters_from_request(request)
        qs_base = ContractSearchService.build_base_queryset()
        qs_display = ContractSearchService.apply_filters(qs_base, filters)

        # Récupération des données avec tous les champs
        rows = list(
            qs_display.values(
                "id",
                "client__lead__first_name",
                "client__lead__last_name",
                "client__lead__email",
                "client__lead__phone",
                "service__label",
                "amount_due",
                "amount_paid",
                "balance_due",
                "is_signed",
                "is_cancelled",
                "created_by__first_name",
                "created_by__last_name",
            ).order_by("-created_at")
        )

        # Création du CSV
        import csv
        from django.http import HttpResponse

        response = HttpResponse(content_type='text/csv')
        response[
            'Content-Disposition'] = f'attachment; filename="contrats_export_{timezone.now().strftime("%Y%m%d_%H%M%S")}.csv"'

        writer = csv.writer(response)
        # En-têtes
        writer.writerow([
            'ID Contrat', 'Nom Client', 'Email', 'Téléphone', 'Service',
            'Montant Service', 'Montant Payé', 'Solde', 'Signé', 'Annulé', 'Créé par'
        ])

        # Données
        for row in rows:
            client_name = f"{row['client__lead__first_name'] or ''} {row['client__lead__last_name'] or ''}".strip()
            created_by_name = f"{row['created_by__first_name'] or ''} {row['created_by__last_name'] or ''}".strip() or 'N/A'

            writer.writerow([
                row['id'],
                client_name,
                row['client__lead__email'] or 'N/A',
                row['client__lead__phone'] or 'N/A',
                row['service__label'] or 'N/A',
                f"{_dec(row['amount_due']):.2f}",
                f"{_dec(row['amount_paid']):.2f}",
                f"{_dec(row['balance_due']):.2f}",
                'Oui' if row['is_signed'] else 'Non',
                'Oui' if row['is_cancelled'] else 'Non',
                created_by_name
            ])

        return response

    def _generate_pdf_response(self, rows, aggregates, total_count):
        """Génère la réponse PDF"""
        buffer = BytesIO()
        doc = SimpleDocTemplate(
            buffer,
            pagesize=landscape(A4),
            rightMargin=1 * cm,
            leftMargin=1 * cm,
            topMargin=1.5 * cm,
            bottomMargin=1.5 * cm,
        )

        elements = []
        styles = getSampleStyleSheet()

        # Style personnalisé pour le titre
        title_style = ParagraphStyle(
            'CustomTitle',
            parent=styles['Heading1'],
            fontSize=18,
            textColor=colors.HexColor('#1a1a1a'),
            spaceAfter=20,
            alignment=1,
        )

        # Titre
        title = Paragraph("Rapport des Contrats - TDS France", title_style)
        elements.append(title)

        # Date de génération
        date_generation = Paragraph(
            f"<b>Généré le :</b> {timezone.now().strftime('%d/%m/%Y à %H:%M')}",
            styles['Normal']
        )
        elements.append(date_generation)
        elements.append(Spacer(1, 0.5 * cm))

        # Section statistiques
        stats_title = Paragraph("<b>Statistiques Globales</b>", styles['Heading2'])
        elements.append(stats_title)
        elements.append(Spacer(1, 0.3 * cm))

        stats_data = [
            ['Indicateur', 'Valeur'],
            ['Nombre total de contrats', str(total_count)],
            ['Montant total dû', f"{ContractSearchService._dec(aggregates['sum_amount_due']):.2f} €"],
            ['Montant réel (après remise)', f"{ContractSearchService._dec(aggregates['sum_real_amount_due']):.2f} €"],
            ['Total payé', f"{ContractSearchService._dec(aggregates['sum_amount_paid']):.2f} €"],
            ['Total net payé', f"{ContractSearchService._dec(aggregates['sum_net_paid']):.2f} €"],
            ['Solde restant dû', f"{ContractSearchService._dec(aggregates['sum_balance_due']):.2f} €"],
            ['Contrats signés', f"{aggregates['count_signed']}"],
            ['Contrats remboursés', f"{aggregates['count_refunded']}"],
            ['Contrats soldés', f"{aggregates['count_fully_paid']}"],
            ['Contrats avec solde', f"{aggregates['count_with_balance']}"],
            ['Contrats avec remise', f"{aggregates['count_reduced']}"],
            ['Contrats annulés', f"{aggregates['count_cancelled']}"],
        ]

        stats_table = Table(stats_data, colWidths=[10 * cm, 8 * cm])
        stats_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#2c3e50')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('ALIGN', (1, 1), (1, -1), 'RIGHT'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 10),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
            ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
            ('GRID', (0, 0), (-1, -1), 1, colors.black),
            ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.lightgrey]),
        ]))

        elements.append(stats_table)
        elements.append(PageBreak())

        # Section détails des contrats
        details_title = Paragraph("<b>Détails des Contrats</b>", styles['Heading2'])
        elements.append(details_title)
        elements.append(Spacer(1, 0.3 * cm))

        # En-têtes du tableau
        contract_data = [
            [
                'ID Contrat',
                'Nom Client',
                'Email',
                'Téléphone',
                'Service',
                'Montant Service',
                'Montant Payé',
                'Solde',
                'Signé',
                'Annulé',
                'Créé par'
            ]
        ]

        # Données des contrats
        for row in rows:
            client_name = f"{row['client__lead__first_name'] or ''} {row['client__lead__last_name'] or ''}".strip()
            email = row['client__lead__email'] or 'N/A'
            phone = row['client__lead__phone'] or 'N/A'
            service_label = row['service__label'] or 'N/A'
            created_by_name = f"{row['created_by__first_name'] or ''} {row['created_by__last_name'] or ''}".strip() or 'N/A'

            contract_data.append([
                str(row['id']),
                client_name,
                email,
                phone,
                service_label,
                f"{ContractSearchService._dec(row['amount_due']):.2f} €",
                f"{ContractSearchService._dec(row['amount_paid']):.2f} €",
                f"{ContractSearchService._dec(row['balance_due']):.2f} €",
                '✓' if row['is_signed'] else '✗',
                '✓' if row['is_cancelled'] else '✗',
                created_by_name
            ])

        # Largeurs des colonnes
        col_widths = [
            2 * cm,  # ID Contrat
            3 * cm,  # Nom Client
            3.5 * cm,  # Email
            2.5 * cm,  # Téléphone
            4 * cm,  # Service
            2 * cm,  # Montant Service
            2 * cm,  # Montant Payé
            2 * cm,  # Solde
            1.5 * cm,  # Signé
            1.5 * cm,  # Annulé
            2.5 * cm  # Créé par
        ]

        contract_table = Table(contract_data, colWidths=col_widths, repeatRows=1)
        contract_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#34495e')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 7),
            ('FONTSIZE', (0, 1), (-1, -1), 6),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 6),
            ('TOPPADDING', (0, 1), (-1, -1), 3),
            ('BOTTOMPADDING', (0, 1), (-1, -1), 3),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
            ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#f8f9fa')]),
            ('WORDWRAP', (0, 0), (-1, -1), True),
        ]))

        elements.append(contract_table)

        # Construction du PDF
        doc.build(elements)
        buffer.seek(0)

        # Réponse HTTP
        response = HttpResponse(buffer.getvalue(), content_type='application/pdf')
        filename = f"contrats_export_{timezone.now().strftime('%Y%m%d_%H%M%S')}.pdf"
        response['Content-Disposition'] = f'attachment; filename="{filename}"'

        return response