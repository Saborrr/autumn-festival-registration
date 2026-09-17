from django import forms
from django.utils.html import format_html, format_html_join

from .models import Registration, Team
from .validators import normalize_russian_phone


CHILD_AGE_ERROR = "Укажите возраст каждого ребёнка от 0 до 17 лет."
MAX_COMPANION_CHILDREN = 10
MAX_COMPANION_CHILDREN_ERROR = (
    f"Можно указать не более {MAX_COMPANION_CHILDREN} сопровождающих детей."
)


class ChildAgesWidget(forms.Widget):
    """Repeatable number inputs whose values are read with QueryDict.getlist()."""

    def value_from_datadict(self, data, files, name):
        return data.getlist(name) if hasattr(data, "getlist") else data.get(name, [])

    def render(self, name, value, attrs=None, renderer=None):
        values = value if isinstance(value, (list, tuple)) else ([] if value is None else [value])
        values = list(values) or [""]
        rows = format_html_join(
            "",
            '<div class="child-age-row" data-child-row>'
            '<label for="id_child_ages_{}">Ребёнок {}</label>'
            '<div class="child-age-controls">'
            '<input type="number" name="{}" id="id_child_ages_{}" value="{}" '
            'min="0" max="17" inputmode="numeric" aria-label="Возраст ребёнка {}">'
            '<button type="button" class="remove-child" data-remove-child '
            'aria-label="Удалить ребёнка {}">Удалить</button>'
            "</div></div>",
            (
                (index, index + 1, name, index, raw, index + 1, index + 1)
                for index, raw in enumerate(values)
            ),
        )
        return format_html(
            '<div class="child-age-rows" data-child-rows data-max-children="{}">{}</div>',
            MAX_COMPANION_CHILDREN,
            rows,
        )


class ChildAgesField(forms.Field):
    widget = ChildAgesWidget

    def to_python(self, value):
        if value is None:
            return []
        return list(value) if isinstance(value, (list, tuple)) else [value]

    def validate(self, value):
        # Conditional validation belongs in RegistrationForm.clean().
        return


class RegistrationForm(forms.ModelForm):
    activities = forms.MultipleChoiceField(
        label="Как вы хотите участвовать",
        choices=Registration.ParticipationFormat.choices,
        widget=forms.CheckboxSelectMultiple,
        error_messages={"required": "Выберите хотя бы один вариант участия."},
    )
    companions = forms.MultipleChoiceField(
        label="Кто придёт с вами",
        choices=Registration.Companions.choices[:3],
        widget=forms.CheckboxSelectMultiple,
        error_messages={"required": "Выберите хотя бы один вариант."},
    )
    child_ages = ChildAgesField(label="Возраст сопровождающих детей", required=False)

    class Meta:
        model = Registration
        fields = (
            "full_name",
            "organization_unit",
            "phone",
            "activities",
            "team",
            "participant_type",
            "child_age",
            "companions",
            "child_ages",
        )
        widgets = {
            "full_name": forms.TextInput(
                attrs={"autocomplete": "name", "placeholder": "Иванов Иван Иванович"}
            ),
            "organization_unit": forms.TextInput(
                attrs={"placeholder": "Предприятие или подразделение"}
            ),
            "phone": forms.TextInput(
                attrs={
                    "autocomplete": "tel",
                    "inputmode": "tel",
                    "maxlength": 18,
                    "pattern": (
                        r"(?:[+]7|7|8)?[ ()-]*[0-9]{3}[ ()-]*[0-9]{3}"
                        r"[ -]*[0-9]{2}[ -]*[0-9]{2}"
                    ),
                    "placeholder": "+7 900 000-00-00",
                }
            ),
            "participant_type": forms.RadioSelect,
            "child_age": forms.NumberInput(attrs={"min": 0, "max": 13}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["team"].queryset = Team.objects.filter(is_active=True).order_by("number")
        self.fields["team"].label = "Команда"
        self.fields["team"].empty_label = "Выберите команду"
        self.fields["team"].required = False
        self.fields["organization_unit"].required = True
        self.fields["phone"].required = True
        self.fields["phone"].widget.attrs["maxlength"] = 18
        self.fields["participant_type"].choices = Registration.ParticipantType.choices
        self.fields["participant_type"].required = False
        self.fields["participant_type"].initial = Registration.ParticipantType.ADULT
        self.fields["child_age"].required = False

        if not self.is_bound:
            companion_initial = {
                Registration.Companions.ALONE: [Registration.Companions.ALONE],
                Registration.Companions.ADULT_RELATIVE: [Registration.Companions.ADULT_RELATIVE],
                Registration.Companions.CHILDREN: [Registration.Companions.CHILDREN],
                Registration.Companions.ADULT_AND_CHILDREN: [
                    Registration.Companions.ADULT_RELATIVE,
                    Registration.Companions.CHILDREN,
                ],
            }
            self.initial["companions"] = companion_initial.get(
                self.instance.companions, [Registration.Companions.ALONE]
            )

        if not self.is_bound and self.instance.pk:
            activities = [self.instance.participation_format]
            if self.instance.participates_in_pie and Registration.ParticipationFormat.PIE not in activities:
                activities.append(Registration.ParticipationFormat.PIE)
            self.initial["activities"] = activities
            self.initial["child_ages"] = list(
                self.instance.companion_children.values_list("age", flat=True)
            )

    def clean_phone(self):
        return normalize_russian_phone(self.cleaned_data["phone"])

    def clean(self):
        cleaned = super().clean()
        activities = set(cleaned.get("activities") or ())
        game = Registration.ParticipationFormat.GAME
        supporter = Registration.ParticipationFormat.SUPPORTER
        pie = Registration.ParticipationFormat.PIE

        if game in activities and supporter in activities:
            self.add_error(
                "activities",
                "Нельзя одновременно выбрать участие в «Большой игре» и роль болельщика.",
            )

        if game in activities:
            participation_format = game
            if not cleaned.get("team"):
                self.add_error("team", "Выберите команду.")
            if not cleaned.get("participant_type"):
                self.add_error("participant_type", "Укажите возрастную категорию участника.")
        else:
            participation_format = supporter if supporter in activities else pie
            cleaned["team"] = None
            cleaned["participant_type"] = ""
            cleaned["child_age"] = None

        self.instance.participation_format = participation_format
        self.instance.participates_in_pie = pie in activities

        companion_options = set(cleaned.get("companions") or ())
        alone = Registration.Companions.ALONE
        adult_relative = Registration.Companions.ADULT_RELATIVE
        children = Registration.Companions.CHILDREN

        if alone in companion_options and len(companion_options) > 1:
            self.add_error(
                "companions",
                "Вариант «Приду один (одна)» нельзя совмещать с другими вариантами.",
            )
            companion_value = None
        elif companion_options == {adult_relative, children}:
            companion_value = Registration.Companions.ADULT_AND_CHILDREN
        elif len(companion_options) == 1:
            companion_value = next(iter(companion_options))
        else:
            companion_value = None

        if companion_value is not None:
            cleaned["companions"] = companion_value
            self.instance.companions = companion_value

        raw_ages = cleaned.get("child_ages") or []
        if children in companion_options and companion_value is not None:
            if len(raw_ages) > MAX_COMPANION_CHILDREN:
                self.add_error("child_ages", MAX_COMPANION_CHILDREN_ERROR)
                cleaned["child_ages"] = []
                return cleaned
            try:
                ages = [int(value) for value in raw_ages]
            except (TypeError, ValueError):
                ages = []
            if not raw_ages or len(ages) != len(raw_ages) or any(age < 0 or age > 17 for age in ages):
                self.add_error("child_ages", CHILD_AGE_ERROR)
            else:
                cleaned["child_ages"] = ages
        else:
            cleaned["child_ages"] = []
        return cleaned

    def save(self, commit=True):
        registration = super().save(commit=False)
        activities = set(self.cleaned_data["activities"])
        if Registration.ParticipationFormat.GAME in activities:
            registration.participation_format = Registration.ParticipationFormat.GAME
        elif Registration.ParticipationFormat.SUPPORTER in activities:
            registration.participation_format = Registration.ParticipationFormat.SUPPORTER
        else:
            registration.participation_format = Registration.ParticipationFormat.PIE
        registration.participates_in_pie = Registration.ParticipationFormat.PIE in activities
        if commit:
            registration.save()
            self.save_m2m()
        return registration
