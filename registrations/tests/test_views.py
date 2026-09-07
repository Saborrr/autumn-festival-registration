from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from registrations.models import Registration, Team


class HomePageTests(TestCase):
    def test_home_lists_all_ten_teams_with_capacity(self):
        response = self.client.get(reverse("home"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Краски осени")
        self.assertEqual(len(response.context["teams"]), 10)
        self.assertContains(response, "0 из 10")
        self.assertContains(response, "19 сентября")
        self.assertContains(response, "Участник «Большой игры»")
        self.assertContains(response, "Болельщик")
        self.assertContains(response, "Конкурс «Счастье в пирогах»")
        self.assertContains(
            response,
            "Дизайн и разработка Александр Фадеев, al.al.fdv@gmail.com",
        )
        self.assertNotContains(response, "Фото:")

    def test_home_shows_active_participants_in_their_team(self):
        team = Team.objects.get(number=1)
        team.registrations.create(
            full_name="Мария Иванова", participant_type="adult"
        )
        team.registrations.create(
            full_name="Павел Орлов",
            participant_type="adult",
            status="cancelled",
        )

        response = self.client.get(reverse("home"))

        self.assertContains(response, "Уже в команде")
        self.assertContains(response, "Мария Иванова")
        self.assertNotContains(response, "Павел Орлов")

    def test_valid_registration_reserves_a_place(self):
        team = Team.objects.get(number=1)

        response = self.client.post(
            reverse("register"),
            {
                "team": team.pk,
                "full_name": "Мария Иванова",
                "organization_unit": "ЭФКО, производство",
                "phone": "+7 900 000-00-00",
                "participation_format": "game",
                "participant_type": "adult",
                "child_age": "",
                "companions": "alone",
                "children_details": "",
            },
        )

        self.assertRedirects(response, reverse("registration_success"))
        self.assertTrue(
            team.registrations.filter(full_name="Мария Иванова").exists()
        )

    def test_registration_is_rejected_when_team_is_full(self):
        team = Team.objects.get(number=1)
        for index in range(10):
            team.registrations.create(
                full_name=f"Участник {index}", participant_type="adult"
            )

        response = self.client.post(
            reverse("register"),
            {
                "team": team.pk,
                "full_name": "Одиннадцатый Участник",
                "organization_unit": "ЭФКО, производство",
                "phone": "+7 900 000-00-00",
                "participation_format": "game",
                "participant_type": "adult",
                "child_age": "",
                "companions": "alone",
                "children_details": "",
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "В этой команде уже нет свободных мест")
        self.assertEqual(team.registrations.count(), 10)

    def test_registration_page_uses_category_neutral_copy(self):
        response = self.client.get(reverse("register") + "?format=pie")

        self.assertContains(response, "Ваш формат")
        self.assertContains(response, "Вернуться к форматам")
        self.assertNotContains(response, "Ваше место<br>в команде", html=True)

    def test_supporter_can_register_without_a_team(self):
        response = self.client.post(
            reverse("register"),
            {
                "team": "",
                "full_name": "Елена Соколова",
                "organization_unit": "ЭФКО, офис",
                "phone": "+7 953 111-22-33",
                "participation_format": "supporter",
                "participant_type": "",
                "child_age": "",
                "companions": "adult_relative",
                "children_details": "",
            },
        )

        self.assertRedirects(response, reverse("registration_success"))
        registration = Team.objects.first().registrations.model.objects.get(
            full_name="Елена Соколова"
        )
        self.assertEqual(registration.participation_format, "supporter")
        self.assertIsNone(registration.team)

    def test_pie_contest_is_a_separate_registration_category(self):
        response = self.client.post(
            reverse("register"),
            {
                "team": "",
                "full_name": "Ольга Пирогова",
                "organization_unit": "ЭФКО, логистика",
                "phone": "+7 953 444-55-66",
                "participation_format": "pie",
                "participant_type": "",
                "child_age": "",
                "companions": "children",
                "children_details": "2 ребёнка, 6 и 9 лет",
            },
        )

        self.assertRedirects(response, reverse("registration_success"))


class ModeratorDashboardTests(TestCase):
    def test_dashboard_requires_staff_and_shows_registrations(self):
        team = Team.objects.get(number=3)
        team.registrations.create(
            full_name="Елена Соколова", participant_type="adult"
        )

        anonymous = self.client.get(reverse("moderator_dashboard"))
        self.assertRedirects(
            anonymous,
            f'{reverse("login")}?next={reverse("moderator_dashboard")}',
        )

        moderator = get_user_model().objects.create_user(
            username="moderator", password="strong-password", is_staff=True
        )
        self.client.force_login(moderator)
        response = self.client.get(reverse("moderator_dashboard"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Елена Соколова")
        self.assertContains(response, "Команда 3")

    def test_staff_can_cancel_registration(self):
        team = Team.objects.get(number=4)
        registration = team.registrations.create(
            full_name="Павел Орлов", participant_type="adult"
        )
        moderator = get_user_model().objects.create_user(
            username="moderator", password="strong-password", is_staff=True
        )
        self.client.force_login(moderator)

        response = self.client.post(
            reverse("moderator_toggle", args=[registration.pk])
        )

        self.assertRedirects(response, reverse("moderator_dashboard"))
        registration.refresh_from_db()
        self.assertEqual(registration.status, registration.Status.CANCELLED)

    def test_staff_cannot_restore_registration_into_full_team(self):
        team = Team.objects.get(number=5)
        cancelled = team.registrations.create(
            full_name="Запасной Участник",
            participant_type="adult",
            status="cancelled",
        )
        for index in range(10):
            team.registrations.create(
                full_name=f"Активный {index}", participant_type="adult"
            )
        moderator = get_user_model().objects.create_user(
            username="moderator", password="strong-password", is_staff=True
        )
        self.client.force_login(moderator)

        response = self.client.post(reverse("moderator_toggle", args=[cancelled.pk]))

        self.assertRedirects(response, reverse("moderator_dashboard"))
        cancelled.refresh_from_db()
        self.assertEqual(cancelled.status, cancelled.Status.CANCELLED)

    def test_dashboard_filters_every_supported_column(self):
        moderator = get_user_model().objects.create_user(
            username="filter-moderator", password="strong-password", is_staff=True
        )
        self.client.force_login(moderator)
        team = Team.objects.get(number=2)
        game = team.registrations.create(
            full_name="Игрок",
            organization_unit="Производство",
            phone="111",
            participation_format="game",
            participant_type="adult",
            companions="alone",
        )
        supporter = Registration.objects.create(
            full_name="Болельщик",
            organization_unit="Офис",
            phone="222",
            participation_format="supporter",
            participant_type="",
            companions="adult_relative",
        )
        pie = Registration.objects.create(
            full_name="Пекарь",
            organization_unit="Логистика",
            phone="333",
            participation_format="pie",
            participant_type="",
            companions="children",
            children_details="1 ребёнок, 8 лет",
            status="cancelled",
        )
        cases = (
            ({"format": "supporter"}, supporter),
            ({"team": str(team.pk)}, game),
            ({"organization_unit": "Логистика"}, pie),
            ({"companions": "alone"}, game),
            ({"status": "cancelled"}, pie),
        )

        for params, expected in cases:
            with self.subTest(params=params):
                response = self.client.get(reverse("moderator_dashboard"), params)
                self.assertEqual(list(response.context["registrations"]), [expected])

    def test_dashboard_sorts_every_supported_column(self):
        moderator = get_user_model().objects.create_user(
            username="sort-moderator", password="strong-password", is_staff=True
        )
        self.client.force_login(moderator)
        team_one = Team.objects.get(number=1)
        team_three = Team.objects.get(number=3)
        alpha = team_one.registrations.create(
            full_name="Альфа",
            organization_unit="Альфа",
            participation_format="game",
            participant_type="adult",
            companions="adult_relative",
            status="active",
        )
        omega = team_three.registrations.create(
            full_name="Омега",
            organization_unit="Омега",
            participation_format="pie",
            participant_type="",
            companions="children",
            children_details="1 ребёнок, 8 лет",
            status="cancelled",
        )
        cases = (
            ("format", "asc", alpha),
            ("team", "desc", omega),
            ("organization_unit", "asc", alpha),
            ("companions", "asc", alpha),
            ("status", "desc", omega),
        )

        for sort, direction, expected_first in cases:
            with self.subTest(sort=sort, direction=direction):
                response = self.client.get(
                    reverse("moderator_dashboard"),
                    {"sort": sort, "direction": direction},
                )
                self.assertEqual(response.context["registrations"][0], expected_first)

    def test_dashboard_does_not_offer_participant_or_phone_sorting(self):
        moderator = get_user_model().objects.create_user(
            username="safe-moderator", password="strong-password", is_staff=True
        )
        self.client.force_login(moderator)

        response = self.client.get(reverse("moderator_dashboard"))

        self.assertNotContains(response, 'value="full_name"')
        self.assertNotContains(response, 'value="phone"')
