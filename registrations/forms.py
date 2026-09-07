from django import forms

from .models import Registration, Team


class RegistrationForm(forms.ModelForm):
    activities = forms.MultipleChoiceField(
        label="Как вы хотите участвовать",
        choices=Registration.ParticipationFormat.choices,
        widget=forms.CheckboxSelectMultiple,
        error_messages={"required": "Выберите хотя бы один вариант участия."},
    )

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
            "children_details",
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
                    "placeholder": "+7 900 000-00-00",
                }
            ),
            "participant_type": forms.RadioSelect,
            "child_age": forms.NumberInput(attrs={"min": 0, "max": 13}),
            "companions": forms.RadioSelect,
            "children_details": forms.TextInput(
                attrs={"placeholder": "Например: 2 ребёнка, 6 и 9 лет"}
            ),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["team"].queryset = Team.objects.order_by("number")
        self.fields["team"].label = "Команда"
        self.fields["team"].empty_label = "Выберите команду"
        self.fields["team"].required = False
        self.fields["organization_unit"].required = True
        self.fields["phone"].required = True
        self.fields["participant_type"].choices = Registration.ParticipantType.choices
        self.fields["participant_type"].required = False
        self.fields["participant_type"].initial = Registration.ParticipantType.ADULT
        self.fields["child_age"].required = False
        self.fields["companions"].choices = Registration.Companions.choices
        self.fields["companions"].initial = Registration.Companions.ALONE
        self.fields["children_details"].required = False

        if not self.is_bound and self.instance.pk:
            activities = [self.instance.participation_format]
            if (
                self.instance.participates_in_pie
                and Registration.ParticipationFormat.PIE not in activities
            ):
                activities.append(Registration.ParticipationFormat.PIE)
            self.initial["activities"] = activities

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
                self.add_error(
                    "participant_type", "Укажите возрастную категорию участника."
                )
        else:
            participation_format = supporter if supporter in activities else pie
            cleaned["team"] = None
            cleaned["participant_type"] = ""
            cleaned["child_age"] = None

        self.instance.participation_format = participation_format
        self.instance.participates_in_pie = pie in activities

        if cleaned.get("companions") == Registration.Companions.CHILDREN:
            if not (cleaned.get("children_details") or "").strip():
                self.add_error(
                    "children_details", "Укажите количество и возраст детей."
                )
        else:
            cleaned["children_details"] = ""
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
