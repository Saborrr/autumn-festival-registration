from django.contrib import messages
from django.contrib.admin.views.decorators import staff_member_required
from django.conf import settings
from django.db import transaction
from django.db.models import Count, Q, Sum
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from .forms import RegistrationForm
from .exports import docx_response, xlsx_response
from .models import CompanionChild, Registration, Team


ADULT_COMPANION_VALUES = (
    Registration.Companions.ADULT_RELATIVE,
    Registration.Companions.ADULT_AND_CHILDREN,
)
CHILD_COMPANION_VALUES = (
    Registration.Companions.CHILDREN,
    Registration.Companions.ADULT_AND_CHILDREN,
)


def aggregate_attendance(queryset):
    """Return registration and people totals in one aggregate query."""
    totals = queryset.aggregate(
        matched_registrations=Count("pk", distinct=True),
        active_main_participants=Count(
            "pk", filter=Q(status=Registration.Status.ACTIVE), distinct=True
        ),
        main_children=Count(
            "pk",
            filter=Q(
                status=Registration.Status.ACTIVE,
                participant_type=Registration.ParticipantType.CHILD,
            ),
            distinct=True,
        ),
        accompanying_adults=Count(
            "pk",
            filter=Q(
                status=Registration.Status.ACTIVE,
                companions__in=ADULT_COMPANION_VALUES,
            ),
            distinct=True,
        ),
        accompanying_children=Count(
            "companion_children",
            filter=Q(
                status=Registration.Status.ACTIVE,
                companions__in=CHILD_COMPANION_VALUES,
            ),
        ),
        legacy_child_records_needing_review=Count(
            "pk",
            filter=(
                Q(status=Registration.Status.ACTIVE)
                & ~Q(children_details="")
                & (
                    Q(companion_children__needs_manual_review=True)
                    | Q(companion_children__isnull=True)
                )
            ),
            distinct=True,
        ),
    )
    totals["total_active_people"] = (
        totals["active_main_participants"]
        + totals["accompanying_adults"]
        + totals["accompanying_children"]
    )
    return totals


def home(request):
    return render(request, "registrations/home.html")


def register(request):
    if not settings.REGISTRATION_OPEN:
        return redirect("home")

    selected_format = request.GET.get("format", Registration.ParticipationFormat.GAME)
    if selected_format not in Registration.ParticipationFormat.values:
        selected_format = Registration.ParticipationFormat.GAME
    if request.GET.get("team"):
        selected_format = Registration.ParticipationFormat.GAME
    initial = {
        "team": request.GET.get("team"),
        "activities": [selected_format],
    }
    form = RegistrationForm(request.POST or None, initial=initial)
    if request.method == "POST" and form.is_valid():
        registration = form.save(commit=False)
        with transaction.atomic():
            if registration.participation_format == Registration.ParticipationFormat.GAME:
                team = (
                    Team.objects.select_for_update()
                    .filter(pk=registration.team_id, is_active=True)
                    .first()
                )
                if team is None:
                    form.add_error("team", "Выберите действующую команду.")
                else:
                    occupied = team.registrations.filter(
                        status=Registration.Status.ACTIVE
                    ).count()
                    if occupied >= team.capacity:
                        form.add_error("team", "В этой команде уже нет свободных мест.")
                    else:
                        registration.team = team
                        registration.save()
            else:
                registration.save()

            if registration.pk and not form.errors:
                CompanionChild.objects.bulk_create(
                    CompanionChild(registration=registration, age=age)
                    for age in form.cleaned_data["child_ages"]
                )
                return redirect("registration_success")
    return render(request, "registrations/register.html", {"form": form})


def registration_success(request):
    return render(request, "registrations/success.html")


@staff_member_required(login_url="login")
def export_registrations_xlsx(request):
    return xlsx_response()


@staff_member_required(login_url="login")
def export_registrations_docx(request):
    return docx_response()


@staff_member_required(login_url="login")
def moderator_dashboard(request):
    all_registrations = Registration.objects.select_related("team").prefetch_related(
        "companion_children"
    )
    global_summary = aggregate_attendance(all_registrations)
    active_teams = Team.objects.filter(is_active=True)
    capacity_total = active_teams.aggregate(total=Sum("capacity"))["total"] or 0
    active_game_total = Registration.objects.filter(
        status=Registration.Status.ACTIVE,
        participation_format=Registration.ParticipationFormat.GAME,
        team__is_active=True,
    ).count()
    global_summary["free_active_team_places"] = max(
        capacity_total - active_game_total, 0
    )

    filters = {
        "format": request.GET.get("format", ""),
        "team": request.GET.get("team", ""),
        "organization_unit": request.GET.get("organization_unit", ""),
        "companions": request.GET.get("companions", ""),
        "status": request.GET.get("status", ""),
    }
    registrations = all_registrations
    valid_formats = {value for value, _ in Registration.ParticipationFormat.choices}
    valid_companions = {value for value, _ in Registration.Companions.choices}
    valid_statuses = {value for value, _ in Registration.Status.choices}
    if filters["format"] == Registration.ParticipationFormat.PIE:
        registrations = registrations.filter(
            Q(participation_format=Registration.ParticipationFormat.PIE)
            | Q(participates_in_pie=True)
        )
    elif filters["format"] in valid_formats:
        registrations = registrations.filter(
            participation_format=filters["format"]
        )
    if filters["team"].isdigit():
        registrations = registrations.filter(team_id=filters["team"])
    elif filters["team"] == "none":
        registrations = registrations.filter(team__isnull=True)
    if filters["organization_unit"]:
        registrations = registrations.filter(
            organization_unit=filters["organization_unit"]
        )
    if filters["companions"] == Registration.Companions.ADULT_RELATIVE:
        registrations = registrations.filter(
            companions__in=(
                Registration.Companions.ADULT_RELATIVE,
                Registration.Companions.ADULT_AND_CHILDREN,
            )
        )
    elif filters["companions"] == Registration.Companions.CHILDREN:
        registrations = registrations.filter(
            companions__in=(
                Registration.Companions.CHILDREN,
                Registration.Companions.ADULT_AND_CHILDREN,
            )
        )
    elif filters["companions"] in valid_companions:
        registrations = registrations.filter(companions=filters["companions"])
    if filters["status"] in valid_statuses:
        registrations = registrations.filter(status=filters["status"])

    filters_applied = any(filters.values())
    filtered_summary = aggregate_attendance(registrations)

    sort_fields = {
        "format": "participation_format",
        "team": "team__number",
        "organization_unit": "organization_unit",
        "companions": "companions",
        "status": "status",
    }
    sort = request.GET.get("sort", "")
    direction = request.GET.get("direction", "asc")
    if sort in sort_fields:
        prefix = "-" if direction == "desc" else ""
        registrations = registrations.order_by(
            f"{prefix}{sort_fields[sort]}", "created_at"
        )
    else:
        sort = ""
        direction = "asc"

    organization_units = (
        Registration.objects.exclude(organization_unit="")
        .values_list("organization_unit", flat=True)
        .distinct()
        .order_by("organization_unit")
    )
    return render(
        request,
        "registrations/moderator_dashboard.html",
        {
            "registrations": registrations,
            "filtered_total": filtered_summary["matched_registrations"],
            "global_summary": global_summary,
            "filtered_summary": filtered_summary,
            "filters_applied": filters_applied,
            # Compatibility aliases for existing integrations.
            "active_total": global_summary["active_main_participants"],
            "children_total": global_summary["main_children"],
            "free_total": global_summary["free_active_team_places"],
            "filters": filters,
            "sort": sort,
            "direction": direction,
            "teams": Team.objects.order_by("number"),
            "organization_units": organization_units,
            "format_choices": Registration.ParticipationFormat.choices,
            "companion_choices": Registration.Companions.choices,
            "status_choices": Registration.Status.choices,
            "sort_options": (
                ("format", "Формат"),
                ("team", "Команда"),
                ("organization_unit", "Подразделение"),
                ("companions", "Сопровождение"),
                ("status", "Статус"),
            ),
        },
    )


@require_POST
@staff_member_required(login_url="login")
def moderator_toggle(request, registration_id):
    with transaction.atomic():
        registration = get_object_or_404(
            Registration.objects.select_for_update().select_related("team"),
            pk=registration_id,
        )
        if registration.status == Registration.Status.ACTIVE:
            registration.status = Registration.Status.CANCELLED
        elif registration.team_id:
            team = Team.objects.select_for_update().get(pk=registration.team_id)
            occupied = team.registrations.filter(
                status=Registration.Status.ACTIVE
            ).count()
            if occupied >= team.capacity:
                messages.error(request, "Команда заполнена — восстановить участника нельзя.")
                return redirect("moderator_dashboard")
            registration.status = Registration.Status.ACTIVE
        else:
            registration.status = Registration.Status.ACTIVE
        registration.save(update_fields=("status", "updated_at"))
    return redirect("moderator_dashboard")
