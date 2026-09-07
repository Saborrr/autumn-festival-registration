from django.contrib import messages
from django.contrib.admin.views.decorators import staff_member_required
from django.db import transaction
from django.db.models import Count, Prefetch, Q
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from .forms import RegistrationForm
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
    initial = {"team": request.GET.get("team")}
    form = RegistrationForm(request.POST or None, initial=initial)
    if request.method == "POST" and form.is_valid():
        with transaction.atomic():
            team = Team.objects.select_for_update().get(pk=form.cleaned_data["team"].pk)
            occupied = team.registrations.filter(
                status=Registration.Status.ACTIVE
            ).count()
            if occupied >= team.capacity:
                form.add_error("team", "В этой команде уже нет свободных мест.")
            else:
                registration = form.save(commit=False)
                registration.team = team
                registration.save()
                return redirect("registration_success")
    return render(request, "registrations/register.html", {"form": form})


def registration_success(request):
    return render(request, "registrations/success.html")


@staff_member_required(login_url="login")
def moderator_dashboard(request):
    registrations = Registration.objects.select_related("team").all()
    active = registrations.filter(status=Registration.Status.ACTIVE)
    active_total = active.count()
    children_total = active.filter(
        participant_type=Registration.ParticipantType.CHILD
    ).count()
    capacity_total = sum(Team.objects.values_list("capacity", flat=True))
    return render(
        request,
        "registrations/moderator_dashboard.html",
        {
            "registrations": registrations,
            "active_total": active_total,
            "children_total": children_total,
            "free_total": max(capacity_total - active_total, 0),
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
        else:
            team = Team.objects.select_for_update().get(pk=registration.team_id)
            occupied = team.registrations.filter(
                status=Registration.Status.ACTIVE
            ).count()
            if occupied >= team.capacity:
                messages.error(request, "Команда заполнена — восстановить участника нельзя.")
                return redirect("moderator_dashboard")
            registration.status = Registration.Status.ACTIVE
        registration.save(update_fields=("status", "updated_at"))
    return redirect("moderator_dashboard")
