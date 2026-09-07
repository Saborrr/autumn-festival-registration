from django.db import migrations


def create_teams(apps, schema_editor):
    Team = apps.get_model("registrations", "Team")
    Team.objects.bulk_create(
        [Team(number=number, capacity=10) for number in range(1, 11)],
        ignore_conflicts=True,
    )


def remove_teams(apps, schema_editor):
    Team = apps.get_model("registrations", "Team")
    Team.objects.filter(number__range=(1, 10)).delete()


class Migration(migrations.Migration):
    dependencies = [("registrations", "0001_initial")]
    operations = [migrations.RunPython(create_teams, remove_teams)]
