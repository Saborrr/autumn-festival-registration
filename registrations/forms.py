from django import forms

from .models import Registration, Team


class RegistrationForm(forms.ModelForm):
    class Meta:
        model = Registration
        fields = (
            "full_name",
            "organization_unit",
            "phone",
            "participation_format",
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
                attrs={"autocomplete": "tel", "inputmode": "tel", "placeholder": "+7 900 000-00-00"}
            ),
            "participation_format": forms.RadioSelect,
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
        self.fields["participation_format"].required = True
        self.fields["participation_format"].choices = Registration.ParticipationFormat.choices
        self.fields["participant_type"].choices = Registration.ParticipantType.choices
        self.fields["participant_type"].required = False
        self.fields["participant_type"].initial = Registration.ParticipantType.ADULT
        self.fields["child_age"].required = False
        self.fields["companions"].choices = Registration.Companions.choices
        self.fields["companions"].initial = Registration.Companions.ALONE
        self.fields["children_details"].required = False

    def clean(self):
        cleaned = super().clean()
        participation_format = cleaned.get("participation_format")
        if participation_format == Registration.ParticipationFormat.GAME:
            if not cleaned.get("team"):
                self.add_error("team", "Выберите команду.")
            if not cleaned.get("participant_type"):
                self.add_error(
                    "participant_type", "Укажите возрастную категорию участника."
                )
        else:
            cleaned["team"] = None
            cleaned["participant_type"] = ""
            cleaned["child_age"] = None
        if cleaned.get("companions") == Registration.Companions.CHILDREN:
            if not (cleaned.get("children_details") or "").strip():
                self.add_error(
                    "children_details", "Укажите количество и возраст детей."
                )
        else:
            cleaned["children_details"] = ""
        return cleaned
