from django.core.exceptions import ValidationError
from django.db import models


class Team(models.Model):
    number = models.PositiveSmallIntegerField(unique=True)
    capacity = models.PositiveSmallIntegerField(default=10)

    class Meta:
        ordering = ("number",)
        verbose_name = "команда"
        verbose_name_plural = "команды"

    def __str__(self):
        return f"Команда {self.number}"


class Registration(models.Model):
    class ParticipantType(models.TextChoices):
        ADULT = "adult", "Взрослый"
        CHILD = "child", "Ребёнок"

    class Status(models.TextChoices):
        ACTIVE = "active", "Участвует"
        CANCELLED = "cancelled", "Отменена"

    team = models.ForeignKey(Team, on_delete=models.PROTECT, related_name="registrations")
    full_name = models.CharField("ФИО участника", max_length=200)
    participant_type = models.CharField(
        "Категория", max_length=10, choices=ParticipantType.choices
    )
    child_age = models.PositiveSmallIntegerField("Возраст ребёнка", null=True, blank=True)
    status = models.CharField(
        "Статус", max_length=10, choices=Status.choices, default=Status.ACTIVE
    )
    created_at = models.DateTimeField("Дата регистрации", auto_now_add=True)
    updated_at = models.DateTimeField("Дата изменения", auto_now=True)

    class Meta:
        ordering = ("team__number", "created_at")
        verbose_name = "регистрация"
        verbose_name_plural = "регистрации"

    def __str__(self):
        return f"{self.full_name} — {self.team}"

    def clean(self):
        super().clean()
        errors = {}
        if self.participant_type == self.ParticipantType.CHILD:
            if self.child_age is None:
                errors["child_age"] = "Укажите возраст ребёнка."
            elif self.child_age >= 14:
                errors["child_age"] = "Для этой категории ребёнок должен быть младше 14 лет."
        elif self.child_age is not None:
            errors["child_age"] = "Возраст указывается только для ребёнка."
        if errors:
            raise ValidationError(errors)
