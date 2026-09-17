from importlib import import_module
from io import BytesIO

from django.contrib.auth import get_user_model
from django.db import connection
from django.db.migrations.executor import MigrationExecutor
from django.forms.models import inlineformset_factory
from django.test import TestCase, TransactionTestCase
from django.urls import reverse
from openpyxl import load_workbook

from registrations.admin import CompanionChildInlineFormSet, RegistrationAdminForm
from registrations.forms import MAX_COMPANION_CHILDREN, RegistrationForm
from registrations.legacy_children import parse_legacy_children_details
from registrations.models import CompanionChild, Registration, Team
from registrations.views import aggregate_attendance


class LegacyChildrenParserTests(TestCase):
    def test_parses_explicit_count_and_ages(self):
        parsed = parse_legacy_children_details("2 ребёнка, 6 и 9 лет")
        self.assertEqual(parsed.ages, (6, 9))
        self.assertFalse(parsed.needs_manual_review)

    def test_explicit_count_without_ages_creates_unknown_rows(self):
        parsed = parse_legacy_children_details("2 ребенка")
        self.assertEqual(parsed.ages, (None, None))
        self.assertTrue(parsed.needs_manual_review)

    def test_count_age_mismatch_is_padded_and_marked(self):
        parsed = parse_legacy_children_details("3 ребёнка: 6 и 9 лет")
        self.assertEqual(parsed.ages, (6, 9, None))
        self.assertTrue(parsed.needs_manual_review)

    def test_parses_historical_numeric_and_word_counts_conservatively(self):
        cases = (
            ("1", (None,)),
            ("2", (None, None)),
            ("Двое детей, возраст 11 лет", (11, None)),
            ("3 ребенка, 8,5,3", (8, 5, 3)),
            ("4 чел: 1 реб и 3 взр", (None,)),
        )
        for text, expected in cases:
            with self.subTest(text=text):
                self.assertEqual(parse_legacy_children_details(text).ages, expected)

    def test_mixed_numeric_text_only_extracts_explicit_age_expressions(self):
        cases = (
            ("2 ребёнка, 6 и 9 лет + 1 взрослый", (6, 9), False),
            ("7 человек, ребёнок 5 лет", (5,), False),
            ("возраст 2 года 6 месяцев", (2,), False),
            ("4 чел: 1 реб и 3 взр", (None,), True),
            ("3 ребенка, 8,5,3", (8, 5, 3), False),
            ("1", (None,), True),
            ("2", (None, None), True),
            ("7 человек", (), True),
            ("3 (14,13,10) все дети в команде", (), True),
        )
        migration_parser = import_module(
            "registrations.migrations.0006_active_teams_and_companion_children"
        ).parse_legacy_children_details
        for text, expected_ages, expected_review in cases:
            with self.subTest(text=text):
                runtime = parse_legacy_children_details(text)
                self.assertEqual(runtime.ages, expected_ages)
                self.assertEqual(runtime.needs_manual_review, expected_review)
                self.assertEqual(
                    migration_parser(text), (expected_ages, expected_review)
                )

    def test_explicit_count_mismatches_are_preserved_and_marked(self):
        for text, expected in (
            ("3 ребёнка, 6 и 9 лет", (6, 9, None)),
            ("1 ребёнок, 5 и 7 лет", (5, 7)),
        ):
            with self.subTest(text=text):
                parsed = parse_legacy_children_details(text)
                self.assertEqual(parsed.ages, expected)
                self.assertTrue(parsed.needs_manual_review)

    def test_team_children_are_not_double_counted_as_companions(self):
        parsed = parse_legacy_children_details("3 (14,13,10) все дети в команде")
        self.assertEqual(parsed.ages, ())
        self.assertTrue(parsed.needs_manual_review)

    def test_ambiguous_total_people_is_not_interpreted_as_children(self):
        parsed = parse_legacy_children_details("7 человек")
        self.assertEqual(parsed.ages, ())
        self.assertTrue(parsed.needs_manual_review)


class MigrationDataTests(TransactionTestCase):
    migrate_from = [("registrations", "0005_allow_combined_companions")]
    migrate_to = [("registrations", "0006_active_teams_and_companion_children")]

    def test_migration_preserves_hidden_team_registration_and_converts_only_obvious_children(self):
        executor = MigrationExecutor(connection)
        executor.migrate(self.migrate_from)
        old_apps = executor.loader.project_state(self.migrate_from).apps
        OldTeam = old_apps.get_model("registrations", "Team")
        OldRegistration = old_apps.get_model("registrations", "Registration")
        hidden = OldTeam.objects.get(number=7)
        obvious = OldRegistration.objects.create(
            team=hidden,
            full_name="История",
            participant_type="adult",
            children_details="2 ребёнка, 6 и 9 лет",
        )
        ambiguous = OldRegistration.objects.create(
            team=hidden,
            full_name="Неоднозначно",
            participant_type="adult",
            children_details="7 человек",
        )

        executor = MigrationExecutor(connection)
        executor.migrate(self.migrate_to)
        apps = executor.loader.project_state(self.migrate_to).apps
        NewTeam = apps.get_model("registrations", "Team")
        NewRegistration = apps.get_model("registrations", "Registration")
        NewChild = apps.get_model("registrations", "CompanionChild")

        self.assertFalse(NewTeam.objects.get(number=7).is_active)
        self.assertTrue(NewRegistration.objects.filter(pk=obvious.pk, team__number=7).exists())
        self.assertEqual(
            NewRegistration.objects.get(pk=obvious.pk).children_details,
            "2 ребёнка, 6 и 9 лет",
        )
        self.assertEqual(
            list(NewChild.objects.filter(registration_id=obvious.pk).values_list("age", flat=True)),
            [6, 9],
        )
        self.assertFalse(NewChild.objects.filter(registration_id=ambiguous.pk).exists())

    def tearDown(self):
        MigrationExecutor(connection).migrate(self.migrate_to)
        super().tearDown()


class ReverseMigrationDataTests(TransactionTestCase):
    migrate_from = [("registrations", "0005_allow_combined_companions")]
    migrate_to = [("registrations", "0006_active_teams_and_companion_children")]

    def test_reverse_serializes_structured_children_without_overwriting_legacy_text(self):
        executor = MigrationExecutor(connection)
        executor.migrate(self.migrate_to)
        apps = executor.loader.project_state(self.migrate_to).apps
        RegistrationAt0006 = apps.get_model("registrations", "Registration")
        ChildAt0006 = apps.get_model("registrations", "CompanionChild")
        structured = RegistrationAt0006.objects.create(
            full_name="Новая структура",
            participation_format="supporter",
            companions="children",
            children_details="",
        )
        ChildAt0006.objects.create(registration=structured, age=6)
        ChildAt0006.objects.create(
            registration=structured, age=None, needs_manual_review=True
        )
        historical = RegistrationAt0006.objects.create(
            full_name="Старый текст",
            participation_format="supporter",
            companions="children",
            children_details="сохранить дословно",
        )
        ChildAt0006.objects.create(registration=historical, age=8)

        executor = MigrationExecutor(connection)
        executor.migrate(self.migrate_from)
        old_apps = executor.loader.project_state(self.migrate_from).apps
        OldRegistration = old_apps.get_model("registrations", "Registration")

        serialized = OldRegistration.objects.get(pk=structured.pk).children_details
        self.assertIn("2", serialized)
        self.assertIn("6", serialized)
        self.assertIn("возраст не указан", serialized)
        self.assertEqual(
            OldRegistration.objects.get(pk=historical.pk).children_details,
            "сохранить дословно",
        )

    def tearDown(self):
        MigrationExecutor(connection).migrate(self.migrate_to)
        super().tearDown()


class TeamVisibilityTests(TestCase):
    def test_migration_keeps_all_teams_but_hides_seven_through_ten(self):
        self.assertEqual(Team.objects.count(), 10)
        self.assertEqual(
            list(Team.objects.filter(is_active=True).values_list("number", flat=True)),
            [1, 2, 3, 4, 5, 6],
        )
        self.assertEqual(
            list(Team.objects.filter(is_active=False).values_list("number", flat=True)),
            [7, 8, 9, 10],
        )

    def test_public_pages_only_offer_active_teams(self):
        home = self.client.get(reverse("home"))
        registration = self.client.get(reverse("register"))
        self.assertEqual([team.number for team in home.context["teams"]], [1, 2, 3, 4, 5, 6])
        self.assertEqual(
            list(registration.context["form"].fields["team"].queryset.values_list("number", flat=True)),
            [1, 2, 3, 4, 5, 6],
        )

    def test_crafted_post_cannot_register_for_inactive_team(self):
        hidden = Team.objects.get(number=7)
        response = self.client.post(reverse("register"), registration_data(team=hidden.pk))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Выберите корректный вариант")
        self.assertFalse(Registration.objects.filter(full_name="Новый Участник").exists())

    def test_moderator_filter_includes_hidden_team_and_historical_row(self):
        hidden = Team.objects.get(number=9)
        historical = hidden.registrations.create(full_name="Исторический", participant_type="adult")
        self.client.force_login(staff_user("hidden-team-staff"))
        response = self.client.get(reverse("moderator_dashboard"), {"team": hidden.pk})
        self.assertContains(response, "Команда 9 (скрыта)")
        self.assertEqual(list(response.context["registrations"]), [historical])


class StructuredCompanionChildrenTests(TestCase):
    def test_form_renders_repeatable_age_controls_not_legacy_details(self):
        response = self.client.get(reverse("register"))
        self.assertContains(response, 'name="child_ages"')
        self.assertContains(response, "Добавить ребёнка")
        self.assertContains(response, "Ребёнок 1")
        self.assertContains(response, 'data-max-children="10"')
        self.assertNotContains(response, 'name="children_details"')

    def test_zero_children_with_injected_ages_ignores_them(self):
        response = self.client.post(
            reverse("register"), registration_data(companions=["alone"], child_ages=["5"])
        )
        self.assertRedirects(response, reverse("registration_success"))
        registration = Registration.objects.get(full_name="Новый Участник")
        self.assertEqual(registration.companion_children.count(), 0)

    def test_one_and_many_child_ages_are_saved_atomically(self):
        for name, ages in (("Один ребёнок", ["0"]), ("Много детей", ["6", "9", "17"])):
            with self.subTest(ages=ages):
                data = registration_data(
                    full_name=name, companions=["children"], child_ages=ages
                )
                response = self.client.post(reverse("register"), data)
                self.assertRedirects(response, reverse("registration_success"))
                registration = Registration.objects.get(full_name=name)
                self.assertEqual(
                    list(registration.companion_children.values_list("age", flat=True)),
                    [int(age) for age in ages],
                )

    def test_rejects_forged_child_count_over_server_limit(self):
        ages = [str(index % 18) for index in range(MAX_COMPANION_CHILDREN + 1)]
        response = self.client.post(
            reverse("register"),
            registration_data(companions=["children"], child_ages=ages),
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Можно указать не более 10 сопровождающих детей")
        self.assertFalse(Registration.objects.filter(full_name="Новый Участник").exists())

    def test_accepts_exactly_server_child_limit(self):
        ages = [str(index) for index in range(MAX_COMPANION_CHILDREN)]
        response = self.client.post(
            reverse("register"),
            registration_data(companions=["children"], child_ages=ages),
        )
        self.assertRedirects(response, reverse("registration_success"))
        registration = Registration.objects.get(full_name="Новый Участник")
        self.assertEqual(registration.companion_children.count(), MAX_COMPANION_CHILDREN)

    def test_children_require_at_least_one_complete_valid_age(self):
        cases = ([], [""], ["18"], ["-1"], ["6", ""])
        for index, ages in enumerate(cases):
            with self.subTest(ages=ages):
                data = registration_data(
                    full_name=f"Ошибка {index}", companions=["children"], child_ages=ages
                )
                response = self.client.post(reverse("register"), data)
                self.assertEqual(response.status_code, 200)
                self.assertContains(response, "Укажите возраст каждого ребёнка от 0 до 17 лет")
                self.assertFalse(Registration.objects.filter(full_name=f"Ошибка {index}").exists())

    def test_display_helper_handles_many_and_unknown_legacy_age(self):
        registration = Registration.objects.create(
            full_name="Семья", participation_format="supporter", companions="children"
        )
        CompanionChild.objects.create(registration=registration, age=6)
        CompanionChild.objects.create(registration=registration, age=9)
        self.assertEqual(registration.companion_children_display, "2 ребёнка: 6 и 9 лет")
        registration.companion_children.all().delete()
        CompanionChild.objects.create(
            registration=registration, age=None, needs_manual_review=True
        )
        self.assertEqual(registration.companion_children_display, "1 ребёнок: возраст не указан")


class PhoneTests(TestCase):
    def test_valid_phone_variants_are_normalized(self):
        cases = (
            ("9123456789", "+7 912 345-67-89"),
            ("79123456789", "+7 912 345-67-89"),
            ("8 (912) 345-67-89", "+7 912 345-67-89"),
            ("74951234567", "+7 495 123-45-67"),
        )
        for index, (value, expected) in enumerate(cases):
            with self.subTest(value=value):
                form = RegistrationForm(registration_data(full_name=f"Телефон {index}", phone=value))
                self.assertTrue(form.is_valid(), form.errors)
                self.assertEqual(form.cleaned_data["phone"], expected)

    def test_invalid_phone_length_or_prefix_is_rejected_in_russian(self):
        for value in ("912345678", "69123456789", "791234567890"):
            with self.subTest(value=value):
                form = RegistrationForm(registration_data(phone=value))
                self.assertFalse(form.is_valid())
                self.assertIn("Введите российский номер", form.errors["phone"][0])

    def test_letters_and_arbitrary_punctuation_are_rejected(self):
        for value in ("call-me-9123456789", "912.345.67.89", "912/345/67/89"):
            with self.subTest(value=value):
                form = RegistrationForm(registration_data(phone=value))
                self.assertFalse(form.is_valid())
                self.assertIn("Введите российский номер", form.errors["phone"][0])

    def test_phone_widget_has_mobile_attributes(self):
        field = RegistrationForm().fields["phone"]
        self.assertEqual(field.widget.attrs["maxlength"], 18)
        self.assertEqual(field.widget.attrs["autocomplete"], "tel")
        self.assertEqual(field.widget.attrs["inputmode"], "tel")
        self.assertEqual(
            field.widget.attrs["pattern"],
            r"(?:[^0-9]*[0-9]){10,11}[^0-9]*",
        )


class AdminInvariantTests(TestCase):
    FormSet = inlineformset_factory(
        Registration,
        CompanionChild,
        formset=CompanionChildInlineFormSet,
        fields=("age", "needs_manual_review"),
        extra=0,
        can_delete=True,
    )

    def admin_form_data(self, registration, **overrides):
        data = {
            "full_name": registration.full_name,
            "organization_unit": registration.organization_unit,
            "phone": registration.phone,
            "participation_format": registration.participation_format,
            "participates_in_pie": registration.participates_in_pie,
            "participant_type": registration.participant_type,
            "child_age": registration.child_age or "",
            "companions": registration.companions,
            "children_details": registration.children_details,
            "status": registration.status,
            "team": registration.team_id or "",
        }
        data.update(overrides)
        return data

    def inline_data(self, rows):
        data = {
            "companion_children-TOTAL_FORMS": str(len(rows)),
            "companion_children-INITIAL_FORMS": str(
                sum(bool(row.get("id")) for row in rows)
            ),
            "companion_children-MIN_NUM_FORMS": "0",
            "companion_children-MAX_NUM_FORMS": "1000",
        }
        for index, row in enumerate(rows):
            for key, value in row.items():
                data[f"companion_children-{index}-{key}"] = value
        return data

    def test_admin_preserves_unchanged_invalid_legacy_phone(self):
        registration = Registration.objects.create(
            full_name="Архивный телефон",
            phone="внутренний 123",
            participation_format="supporter",
            companions="alone",
        )
        form = RegistrationAdminForm(
            self.admin_form_data(registration), instance=registration
        )
        self.assertTrue(form.is_valid(), form.errors)
        self.assertEqual(form.cleaned_data["phone"], "внутренний 123")

    def test_admin_validates_and_normalizes_changed_phone(self):
        registration = Registration.objects.create(
            full_name="Телефон администратора",
            phone="старый",
            participation_format="supporter",
            companions="alone",
        )
        invalid = RegistrationAdminForm(
            self.admin_form_data(registration, phone="call-me-9123456789"),
            instance=registration,
        )
        self.assertFalse(invalid.is_valid())
        valid = RegistrationAdminForm(
            self.admin_form_data(registration, phone="8 (912) 345-67-89"),
            instance=registration,
        )
        self.assertTrue(valid.is_valid(), valid.errors)
        self.assertEqual(valid.cleaned_data["phone"], "+7 912 345-67-89")

    def test_admin_child_modes_require_a_row_unless_legacy_text_is_retained(self):
        registration = Registration.objects.create(
            full_name="Дети без строки",
            participation_format="supporter",
            companions="children",
        )
        empty = self.FormSet(
            self.inline_data([]), instance=registration, prefix="companion_children"
        )
        self.assertFalse(empty.is_valid())
        self.assertIn("добавьте хотя бы одного", str(empty.non_form_errors()).lower())

        registration.children_details = "старая запись на проверку"
        registration.save(update_fields=("children_details",))
        legacy = self.FormSet(
            self.inline_data([]), instance=registration, prefix="companion_children"
        )
        self.assertTrue(legacy.is_valid(), legacy.non_form_errors())

    def test_admin_non_child_mode_rejects_active_child_rows(self):
        registration = Registration.objects.create(
            full_name="Противоречие",
            participation_format="supporter",
            companions="alone",
        )
        child = CompanionChild.objects.create(registration=registration, age=5)
        formset = self.FormSet(
            self.inline_data(
                [{"id": str(child.pk), "age": "5", "needs_manual_review": ""}]
            ),
            instance=registration,
            prefix="companion_children",
        )
        self.assertFalse(formset.is_valid())
        self.assertIn("не допускаются", str(formset.non_form_errors()).lower())

    def test_admin_requires_valid_age_for_new_or_changed_rows_but_keeps_legacy_null(self):
        registration = Registration.objects.create(
            full_name="Возраст детей",
            participation_format="supporter",
            companions="children",
        )
        new_blank = self.FormSet(
            self.inline_data([{"age": "", "needs_manual_review": ""}]),
            instance=registration,
            prefix="companion_children",
        )
        self.assertFalse(new_blank.is_valid())

        child = CompanionChild.objects.create(
            registration=registration, age=None, needs_manual_review=True
        )
        unchanged_null = self.FormSet(
            self.inline_data(
                [{"id": str(child.pk), "age": "", "needs_manual_review": "on"}]
            ),
            instance=registration,
            prefix="companion_children",
        )
        self.assertTrue(unchanged_null.is_valid(), unchanged_null.errors)

        changed_null = self.FormSet(
            self.inline_data(
                [{"id": str(child.pk), "age": "", "needs_manual_review": ""}]
            ),
            instance=registration,
            prefix="companion_children",
        )
        self.assertFalse(changed_null.is_valid())
        self.assertIn("от 0 до 17", str(changed_null.non_form_errors()))


class AttendanceSummaryTests(TestCase):
    def setUp(self):
        self.staff = staff_user("summary-staff")
        active = Registration.objects.create(
            full_name="Активный ребёнок", participation_format="supporter",
            participant_type="child", child_age=10, companions="adult_and_children",
        )
        CompanionChild.objects.create(registration=active, age=4)
        CompanionChild.objects.create(registration=active, age=7)
        Registration.objects.create(
            full_name="Отменённый", participation_format="supporter",
            companions="adult_relative", status="cancelled",
        )

    def test_aggregate_attendance_counts_active_people_without_n_plus_one(self):
        summary = aggregate_attendance(Registration.objects.all())
        self.assertEqual(summary["matched_registrations"], 2)
        self.assertEqual(summary["active_main_participants"], 1)
        self.assertEqual(summary["main_children"], 1)
        self.assertEqual(summary["accompanying_adults"], 1)
        self.assertEqual(summary["accompanying_children"], 2)
        self.assertEqual(summary["total_active_people"], 4)
        self.assertEqual(summary["legacy_child_records_needing_review"], 0)

    def test_aggregate_ignores_child_rows_for_non_child_companion_modes(self):
        contradictory = Registration.objects.create(
            full_name="Противоречивая ORM запись",
            participation_format="supporter",
            companions="alone",
        )
        CompanionChild.objects.create(registration=contradictory, age=4)
        summary = aggregate_attendance(
            Registration.objects.filter(pk=contradictory.pk)
        )
        self.assertEqual(summary["accompanying_children"], 0)
        self.assertEqual(summary["total_active_people"], 1)

    def test_aggregate_flags_unresolved_legacy_children_without_guessing(self):
        Registration.objects.create(
            full_name="Неясная старая запись",
            participation_format="supporter",
            companions="children",
            children_details="7 человек",
        )
        summary = aggregate_attendance(
            Registration.objects.filter(full_name="Неясная старая запись")
        )
        self.assertEqual(summary["accompanying_children"], 0)
        self.assertEqual(summary["legacy_child_records_needing_review"], 1)

    def test_dashboard_shows_explicit_global_and_filtered_summaries(self):
        self.client.force_login(self.staff)
        response = self.client.get(reverse("moderator_dashboard"), {"status": "cancelled"})
        for text in (
            "активных регистраций / основных участников", "детей среди основных участников",
            "сопровождающих взрослых", "сопровождающих детей",
            "всего ожидается человек с сопровождением", "свободных мест в активных командах",
            "Найдено регистраций: 1", "Активных основных участников: 0",
            "Всего активных людей: 0",
        ):
            self.assertContains(response, text)

    def test_table_has_ordinal_column_and_correct_empty_colspan(self):
        self.client.force_login(self.staff)
        response = self.client.get(reverse("moderator_dashboard"))
        self.assertContains(response, "<th>№</th>", html=True)
        self.assertContains(response, "<td>1</td>", html=True)
        empty = self.client.get(reverse("moderator_dashboard"), {"organization_unit": "нет"})
        self.assertContains(empty, 'colspan="9"')


class StructuredChildrenExportTests(TestCase):
    def test_exports_include_structured_children_summary(self):
        registration = Registration.objects.create(
            full_name="Экспорт Семьи", participation_format="supporter", companions="children"
        )
        CompanionChild.objects.create(registration=registration, age=6)
        CompanionChild.objects.create(registration=registration, age=9)
        self.client.force_login(staff_user("structured-export"))
        response = self.client.get(reverse("export_registrations_xlsx"))
        rows = list(load_workbook(BytesIO(response.content), read_only=True)["Регистрации"].values)
        self.assertIn("2 ребёнка: 6 и 9 лет", rows[1][7])


def registration_data(**overrides):
    data = {
        "team": Team.objects.get(number=1).pk,
        "full_name": "Новый Участник",
        "organization_unit": "Подразделение",
        "phone": "+7 912 345-67-89",
        "activities": ["game"],
        "participant_type": "adult",
        "child_age": "",
        "companions": ["alone"],
        "child_ages": [],
    }
    data.update(overrides)
    return data


def staff_user(username):
    return get_user_model().objects.create_user(
        username=username, password="strong-password", is_staff=True
    )
