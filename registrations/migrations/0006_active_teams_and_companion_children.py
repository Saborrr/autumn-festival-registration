# Generated for the structured companion-child and active-team release.
import re

import django.core.validators
import django.db.models.deletion
from django.db import migrations, models


_CHILD_COUNT_RE = re.compile(
    r"(?P<count>\d+)\s*(?:реб(?:[её]н(?:ок|ка|ку|ком|ке))?|дет(?:ей|и|ям|ьми)?)",
    re.IGNORECASE,
)
_WORD_CHILD_COUNT_RE = re.compile(
    r"\b(?P<count_word>один|одна|одно|двое|трое)\s+(?:реб[её]нок|дет(?:ей|и))",
    re.IGNORECASE,
)
_WORD_COUNTS = {"один": 1, "одна": 1, "одно": 1, "двое": 2, "трое": 3}
_AGE_EXPRESSION_RE = re.compile(
    r"(?P<ages>\d{1,2}(?:\s*(?:,|и)\s*\d{1,2})*)\s*(?:лет|год|года)\b",
    re.IGNORECASE,
)
_SAFE_TRAILING_AGES_RE = re.compile(
    r"^\s*[:,;\-]?\s*(?P<ages>\d{1,2}(?:\s*(?:,|и)\s*\d{1,2})*)\s*[.!]?\s*$",
    re.IGNORECASE,
)
_NUMBER_RE = re.compile(r"\d+")
_ONLY_NUMBER_RE = re.compile(r"^\s*(?P<count>[12])\s*$")
_TEAM_CHILDREN_RE = re.compile(r"дети\s+в\s+команде", re.IGNORECASE)


def parse_legacy_children_details(value):
    """Migration-local mirror; never import the mutable runtime parser."""
    text = (value or "").strip()
    if not text:
        return (), False

    if _TEAM_CHILDREN_RE.search(text):
        return (), True

    count_match = _CHILD_COUNT_RE.search(text)
    word_count_match = _WORD_CHILD_COUNT_RE.search(text)
    only_number_match = _ONLY_NUMBER_RE.fullmatch(text)
    if count_match:
        explicit_count = int(count_match.group("count"))
        matched_count = count_match
    elif word_count_match:
        explicit_count = _WORD_COUNTS[word_count_match.group("count_word").lower()]
        matched_count = word_count_match
    elif only_number_match:
        explicit_count = int(only_number_match.group("count"))
        matched_count = only_number_match
    else:
        explicit_count = None
        matched_count = None

    ages = []
    for age_match in _AGE_EXPRESSION_RE.finditer(text):
        ages.extend(
            number
            for number in (
                int(raw) for raw in _NUMBER_RE.findall(age_match.group("ages"))
            )
            if 0 <= number <= 17
        )

    if not ages and matched_count is not None and (count_match or word_count_match):
        trailing_match = _SAFE_TRAILING_AGES_RE.fullmatch(
            text[matched_count.end() :]
        )
        if trailing_match:
            ages = [
                number
                for number in (
                    int(raw)
                    for raw in _NUMBER_RE.findall(trailing_match.group("ages"))
                )
                if 0 <= number <= 17
            ]

    if explicit_count is None:
        return tuple(ages), not bool(ages)

    target_count = max(explicit_count, len(ages))
    mismatch = len(ages) != explicit_count
    padded = list(ages)
    padded.extend([None] * (target_count - len(padded)))
    return tuple(padded), mismatch or any(age is None for age in padded)


def preserve_teams_and_migrate_children(apps, schema_editor):
    Team = apps.get_model("registrations", "Team")
    Registration = apps.get_model("registrations", "Registration")
    CompanionChild = apps.get_model("registrations", "CompanionChild")

    Team.objects.filter(number__in=(7, 8, 9, 10)).update(is_active=False)

    children = []
    for registration in Registration.objects.exclude(children_details="").iterator():
        ages, needs_manual_review = parse_legacy_children_details(
            registration.children_details
        )
        children.extend(
            CompanionChild(
                registration_id=registration.pk,
                age=age,
                needs_manual_review=needs_manual_review or age is None,
            )
            for age in ages
        )
    CompanionChild.objects.bulk_create(children)


def serialize_structured_children_for_reverse(apps, schema_editor):
    Registration = apps.get_model("registrations", "Registration")
    CompanionChild = apps.get_model("registrations", "CompanionChild")

    for registration in Registration.objects.filter(children_details="").iterator():
        ages = list(
            CompanionChild.objects.filter(registration_id=registration.pk)
            .order_by("id")
            .values_list("age", flat=True)
        )
        if not ages:
            continue
        count = len(ages)
        last_two = count % 100
        last = count % 10
        noun = (
            "ребёнок"
            if last == 1 and last_two != 11
            else "ребёнка"
            if 2 <= last <= 4 and not 12 <= last_two <= 14
            else "детей"
        )
        known_ages = [age for age in ages if age is not None]
        unknown_count = count - len(known_ages)
        details = []
        if known_ages:
            details.append(f"{', '.join(str(age) for age in known_ages)} лет")
        if unknown_count:
            details.append(f"возраст не указан у {unknown_count}")
        Registration.objects.filter(pk=registration.pk, children_details="").update(
            children_details=f"{count} {noun}: {'; '.join(details)}"
        )


class Migration(migrations.Migration):
    dependencies = [("registrations", "0005_allow_combined_companions")]

    operations = [
        migrations.AddField(
            model_name="team",
            name="is_active",
            field=models.BooleanField(default=True, verbose_name="Показывать команду"),
        ),
        migrations.CreateModel(
            name="CompanionChild",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                (
                    "age",
                    models.PositiveSmallIntegerField(
                        blank=True,
                        null=True,
                        validators=[django.core.validators.MaxValueValidator(17)],
                        verbose_name="Возраст",
                    ),
                ),
                ("needs_manual_review", models.BooleanField(default=False, verbose_name="Нужна ручная проверка")),
                (
                    "registration",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="companion_children",
                        to="registrations.registration",
                    ),
                ),
            ],
            options={
                "verbose_name": "сопровождающий ребёнок",
                "verbose_name_plural": "сопровождающие дети",
                "ordering": ("id",),
            },
        ),
        migrations.RunPython(
            preserve_teams_and_migrate_children,
            reverse_code=serialize_structured_children_for_reverse,
        ),
    ]
