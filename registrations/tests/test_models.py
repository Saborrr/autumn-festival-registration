from django.core.exceptions import ValidationError
from django.test import TestCase

from registrations.models import Registration, Team


class RegistrationValidationTests(TestCase):
    def setUp(self):
        self.team = Team.objects.get(number=1)

    def test_child_requires_age_under_fourteen(self):
        registration = Registration(
            team=self.team,
            full_name="Анна Петрова",
            participant_type=Registration.ParticipantType.CHILD,
        )

        with self.assertRaisesMessage(ValidationError, "Укажите возраст ребёнка"):
            registration.full_clean()

        registration.child_age = 14
        with self.assertRaisesMessage(ValidationError, "младше 14 лет"):
            registration.full_clean()

    def test_adult_cannot_have_child_age(self):
        registration = Registration(
            team=self.team,
            full_name="Иван Петров",
            participant_type=Registration.ParticipantType.ADULT,
            child_age=8,
        )

        with self.assertRaisesMessage(ValidationError, "Возраст указывается только для ребёнка"):
            registration.full_clean()
