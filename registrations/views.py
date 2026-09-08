from django.contrib import messages
from django.contrib.admin.views.decorators import staff_member_required
from django.db import transaction
from django.db.models import Count, Prefetch, Q
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from .forms import RegistrationForm
from .exports import docx_response, xlsx_response
from .models import Registration, Team


def home(request):
    teams = Team.objects.annotate(
        active_count=Count(
            "registrations",
            filter=Q(registrations__status=Registration.Status.ACTIVE),
        ),
        child_count=Count(
            "registrations",
            filter=Q(
                registrations__status=Registration.Status.ACTIVE,
                registrations__participant_type=Registration.ParticipantType.CHILD,
            ),
        ),
    ).prefetch_related(
        Prefetch(
            "registrations",
            queryset=Registration.objects.filter(
                status=Registration.Status.ACTIVE
            ).order_by("created_at"),
            to_attr="active_participants",
        )
    )
    teams = list(teams)
    for team in teams:
        team.free_count = max(team.capacity - team.active_count, 0)
    return render(request, "registrations/home.html", {"teams": teams})


def register(request):
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
        if registration.participation_format == Registration.ParticipationFormat.GAME:
            with transaction.atomic():
                team = Team.objects.select_for_update().get(pk=registration.team_id)
                occupied = team.registrations.filter(
                    status=Registration.Status.ACTIVE
                ).count()
                if occupied >= team.capacity:
                    form.add_error("team", "В этой команде уже нет свободных мест.")
                else:
                    registration.team = team
                    registration.save()
                    return redirect("registration_success")
        else:
            registration.save()
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
    all_registrations = Registration.objects.select_related("team").all()
    active = all_registrations.filter(status=Registration.Status.ACTIVE)
    active_total = active.count()
    children_total = active.filter(
        participant_type=Registration.ParticipantType.CHILD
    ).count()
    game_active_total = active.filter(
        participation_format=Registration.ParticipationFormat.GAME
    ).count()
    capacity_total = sum(Team.objects.values_list("capacity", flat=True))

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
            "filtered_total": registrations.count(),
            "active_total": active_total,
            "children_total": children_total,
            "free_total": max(capacity_total - game_active_total, 0),
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
