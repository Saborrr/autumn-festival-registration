from django import forms

from .models import Registration, Team


class RegistrationForm(forms.ModelForm):
    class Meta:
        model = Registration
        fields = ("team", "full_name", "participant_type", "child_age")
        widgets = {
            "full_name": forms.TextInput(
                attrs={"autocomplete": "name", "placeholder": "Иванов Иван Иванович"}
            ),
            "participant_type": forms.RadioSelect,
            "child_age": forms.NumberInput(attrs={"min": 0, "max": 13}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["team"].queryset = Team.objects.order_by("number")
        self.fields["team"].label = "Команда"
        self.fields["team"].empty_label = None
        self.fields["participant_type"].choices = Registration.ParticipantType.choices
        self.fields["participant_type"].initial = Registration.ParticipantType.ADULT
