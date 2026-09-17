from django.core.exceptions import ValidationError
from django.core.validators import MaxValueValidator
from django.db import models


class Team(models.Model):
    number = models.PositiveSmallIntegerField(unique=True)
    capacity = models.PositiveSmallIntegerField(default=10)
    is_active = models.BooleanField("Показывать команду", default=True)

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

    @property
    def companion_children_display(self):
        children = list(self.companion_children.all())
        count = len(children)
        if not count:
            return ""
        last_two = count % 100
        last = count % 10
        noun = "ребёнок" if last == 1 and last_two != 11 else (
            "ребёнка" if 2 <= last <= 4 and not 12 <= last_two <= 14 else "детей"
        )
        ages = [child.age for child in children]
        if all(age is not None for age in ages):
            age_text = " и ".join(str(age) for age in ages) + " лет"
        else:
            labels = [
                f"{age} лет" if age is not None else "возраст не указан"
                for age in ages
            ]
            age_text = ", ".join(labels[:-1]) + (
                f" и {labels[-1]}" if len(labels) > 1 else labels[0]
            )
        return f"{count} {noun}: {age_text}"

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
        if errors:
            raise ValidationError(errors)


class CompanionChild(models.Model):
    registration = models.ForeignKey(
        Registration,
        on_delete=models.CASCADE,
        related_name="companion_children",
    )
    age = models.PositiveSmallIntegerField(
        "Возраст",
        null=True,
        blank=True,
        validators=[MaxValueValidator(17)],
    )
    needs_manual_review = models.BooleanField("Нужна ручная проверка", default=False)

    class Meta:
        ordering = ("id",)
        verbose_name = "сопровождающий ребёнок"
        verbose_name_plural = "сопровождающие дети"

    def __str__(self):
        age = f"{self.age} лет" if self.age is not None else "возраст не указан"
        return f"{self.registration.full_name}: {age}"
