from django.contrib import admin

from .models import Registration, Team


@admin.register(Team)
class TeamAdmin(admin.ModelAdmin):
    list_display = ("number", "capacity", "active_count", "children_count")
    ordering = ("number",)

    @admin.display(description="Участников")
    def active_count(self, obj):
        return obj.registrations.filter(status=Registration.Status.ACTIVE).count()

    @admin.display(description="Детей")
    def children_count(self, obj):
        return obj.registrations.filter(
            status=Registration.Status.ACTIVE,
            participant_type=Registration.ParticipantType.CHILD,
        ).count()


@admin.register(Registration)
class RegistrationAdmin(admin.ModelAdmin):
    list_display = (
        "full_name",
        "participation",
        "team",
        "organization_unit",
        "phone",
        "participant_type",
        "child_age",
        "status",
        "created_at",
    )
    list_filter = (
        "participation_format",
        "participates_in_pie",
        "team",
        "participant_type",
        "status",
    )
    search_fields = ("full_name", "organization_unit", "phone")
    list_select_related = ("team",)
    date_hierarchy = "created_at"

    @admin.display(description="Формат участия", ordering="participation_format")
    def participation(self, obj):
        return obj.participation_display


admin.site.site_header = "Краски осени — администрирование"
admin.site.site_title = "Краски осени"
admin.site.index_title = "Управление регистрацией"
