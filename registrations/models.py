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
    class ParticipationFormat(models.TextChoices):
        GAME = "game", "Участник «Большой игры»"
        SUPPORTER = "supporter", "Болельщик"
        PIE = "pie", "Конкурс «Счастье в пирогах»"

    class ParticipantType(models.TextChoices):
        ADULT = "adult", "Взрослый"
        CHILD = "child", "Ребёнок"

    class Status(models.TextChoices):
        ACTIVE = "active", "Участвует"
        CANCELLED = "cancelled", "Отменена"

    class Companions(models.TextChoices):
        ALONE = "alone", "Приду один (одна)"
        ADULT_RELATIVE = "adult_relative", "Со мной будет 1 взрослый родственник"
        CHILDREN = "children", "Со мной будет ребёнок (дети)"
        ADULT_AND_CHILDREN = (
            "adult_and_children",
            "Со мной будут 1 взрослый родственник и ребёнок (дети)",
        )

    team = models.ForeignKey(
        Team,
        on_delete=models.PROTECT,
        related_name="registrations",
        null=True,
        blank=True,
    )
    full_name = models.CharField("ФИО участника", max_length=200)
    organization_unit = models.CharField(
        "Предприятие, подразделение", max_length=200, blank=True, default=""
    )
    phone = models.CharField("Телефон для связи", max_length=40, blank=True, default="")
    participation_format = models.CharField(
        "Форма участия",
        max_length=12,
        choices=ParticipationFormat.choices,
        default=ParticipationFormat.GAME,
    )
    participates_in_pie = models.BooleanField(
        "Участвует в конкурсе «Счастье в пирогах»", default=False
    )
    participant_type = models.CharField(
        "Возрастная категория",
        max_length=10,
        choices=ParticipantType.choices,
        blank=True,
    )
    child_age = models.PositiveSmallIntegerField("Возраст ребёнка", null=True, blank=True)
    companions = models.CharField(
        "Кто придёт с вами",
        max_length=20,
        choices=Companions.choices,
        default=Companions.ALONE,
    )
    children_details = models.CharField(
        "Возраст и количество детей", max_length=200, blank=True, default=""
    )
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

    @property
    def participation_display(self):
        labels = [self.get_participation_format_display()]
        if (
            self.participates_in_pie
            and self.participation_format != self.ParticipationFormat.PIE
        ):
            labels.append(dict(self.ParticipationFormat.choices)[self.ParticipationFormat.PIE])
        return " + ".join(labels)

    def clean(self):
        super().clean()
        errors = {}
        if self.participation_format == self.ParticipationFormat.GAME and not self.team_id:
            errors["team"] = "Выберите команду."
        if self.participation_format == self.ParticipationFormat.GAME and not self.participant_type:
            errors["participant_type"] = "Укажите возрастную категорию участника."
        if self.participation_format != self.ParticipationFormat.GAME and self.team_id:
            errors["team"] = "Команда выбирается только для участника «Большой игры»."
        if self.participation_format != self.ParticipationFormat.GAME and self.participant_type:
            errors["participant_type"] = "Возрастная категория нужна только участнику игры."
        if self.participant_type == self.ParticipantType.CHILD:
            if self.child_age is None:
                errors["child_age"] = "Укажите возраст ребёнка."
            elif self.child_age >= 14:
                errors["child_age"] = "Для этой категории ребёнок должен быть младше 14 лет."
        elif self.child_age is not None:
            errors["child_age"] = "Возраст указывается только для ребёнка."
        if self.companions in {
            self.Companions.CHILDREN,
            self.Companions.ADULT_AND_CHILDREN,
        } and not self.children_details.strip():
            errors["children_details"] = "Укажите количество и возраст детей."
        if errors:
            raise ValidationError(errors)
