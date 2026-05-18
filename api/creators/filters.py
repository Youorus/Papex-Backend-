import django_filters

from api.creators.models import CreatorProfile, SocialAccountLead


class CreatorProfileFilter(django_filters.FilterSet):
    commission_rate_min = django_filters.NumberFilter(
        field_name="commission_rate",
        lookup_expr="gte",
    )
    commission_rate_max = django_filters.NumberFilter(
        field_name="commission_rate",
        lookup_expr="lte",
    )
    created_at_after = django_filters.DateTimeFilter(
        field_name="created_at",
        lookup_expr="gte",
    )
    created_at_before = django_filters.DateTimeFilter(
        field_name="created_at",
        lookup_expr="lte",
    )
    is_active = django_filters.BooleanFilter(
        field_name="user__is_active",
    )

    class Meta:
        model = CreatorProfile
        fields = [
            "status",
            "country",
            "city",
            "commission_rate_min",
            "commission_rate_max",
            "created_at_after",
            "created_at_before",
            "is_active",
        ]


class SocialAccountLeadFilter(django_filters.FilterSet):
    followers_min = django_filters.NumberFilter(
        field_name="followers_count",
        lookup_expr="gte",
    )
    followers_max = django_filters.NumberFilter(
        field_name="followers_count",
        lookup_expr="lte",
    )
    created_at_after = django_filters.DateTimeFilter(
        field_name="created_at",
        lookup_expr="gte",
    )
    created_at_before = django_filters.DateTimeFilter(
        field_name="created_at",
        lookup_expr="lte",
    )
    has_creator = django_filters.BooleanFilter(
        method="filter_has_creator",
    )

    country = django_filters.CharFilter(
        field_name="country",
        lookup_expr="iexact",
    )
    language = django_filters.CharFilter(
        field_name="language",
        lookup_expr="iexact",
    )
    categories = django_filters.CharFilter(
        field_name="categories",
        lookup_expr="icontains",
    )
    source = django_filters.CharFilter(
        field_name="source",
        lookup_expr="icontains",
    )

    def filter_has_creator(self, queryset, name, value):
        if value is True:
            return queryset.filter(creator__isnull=False)

        if value is False:
            return queryset.filter(creator__isnull=True)

        return queryset

    class Meta:
        model = SocialAccountLead
        fields = [
            "platform",
            "contact_status",
            "is_viable",
            "has_creator",
            "followers_min",
            "followers_max",
            "created_at_after",
            "created_at_before",
            "country",
            "language",
            "categories",
            "source",
        ]