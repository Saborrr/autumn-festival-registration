from django import forms
from django.contrib import admin
from django.core.exceptions import ValidationError
from django.forms.models import BaseInlineFormSet

from .models import CompanionChild, Registration, Team
from .validators import normalize_russian_phone


class RegistrationAdminForm(forms.ModelForm):
    class Meta:
        model = Registration
        fields = "__all__"

    def clean_phone(self):
        phone = self.cleaned_data.get("phone", "")
        if self.instance.pk and "phone" not in self.changed_data:
            return self.instance.phone
        return normalize_russian_phone(phone)


class CompanionChildInlineFormSet(BaseInlineFormSet):
    child_companion_values = {
        Registration.Companions.CHILDREN,
        Registration.Companions.ADULT_AND_CHILDREN,
    }

    def clean(self):
        super().clean()
        if any(self.errors):
            return

        active_forms = [
            form
            for form in self.forms
            if form.cleaned_data
            and not form.cleaned_data.get("DELETE", False)
            and (form.instance.pk or form.has_changed())
        ]
        has_child_companions = self.instance.companions in self.child_companion_values

        if not has_child_companions and active_forms:
            raise ValidationError(
                "Для выбранного режима сопровождения строки детей не допускаются."
            )

        retained_legacy_details = bool(
            self.instance.pk and self.instance.children_details.strip()
        )
        if has_child_companions and not active_forms and not retained_legacy_details:
            raise ValidationError(
                "Для сопровождения с детьми добавьте хотя бы одного ребёнка."
            )

        for form in active_forms:
            if form.has_changed() and form.cleaned_data.get("age") is None:
                raise ValidationError(
                    "Для новых или изменённых строк укажите возраст от 0 до 17 лет."
                )


class CompanionChildInline(admin.TabularInline):
    model = CompanionChild
    formset = CompanionChildInlineFormSet
    extra = 0
    fields = ("age", "needs_manual_review")


@admin.register(Team)
class TeamAdmin(admin.ModelAdmin):
    list_display = ("number", "capacity", "is_active", "active_count", "children_count")
    list_filter = ("is_active",)
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
    form = RegistrationAdminForm
    change_list_template = "admin/registrations/registration/change_list.html"
    inlines = (CompanionChildInline,)
    list_display = (
        "full_name",
        "participation",
        "team",
        "organization_unit",
        "phone",
        "participant_type",
        "child_age",
        "structured_children",
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

    def get_queryset(self, request):
        return super().get_queryset(request).prefetch_related("companion_children")

    @admin.display(description="Формат участия", ordering="participation_format")
    def participation(self, obj):
        return obj.participation_display

    @admin.display(description="Сопровождающие дети")
    def structured_children(self, obj):
        return obj.companion_children_display or "—"


admin.site.site_header = "Краски осени — администрирование"
admin.site.site_title = "Краски осени"
admin.site.index_title = "Управление регистрацией"
