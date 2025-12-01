from django.db import migrations, models
import django.db.models.deletion
import django.utils.timezone
from django.core.validators import MinValueValidator
from django.conf import settings


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='JuristGlobalAvailability',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('availability_type', models.CharField(choices=[('global', 'Disponibilité globale'), ('specific', 'Juriste spécifique')], default='global', help_text='Type de disponibilité : globale ou pour un juriste spécifique', max_length=20)),
                ('date', models.DateField(default=django.utils.timezone.now, help_text='Date du créneau de disponibilité')),
                ('start_time', models.TimeField(help_text='Heure de début du créneau (HH:MM)')),
                ('end_time', models.TimeField(help_text='Heure de fin du créneau (HH:MM)')),
                ('slot_duration', models.IntegerField(default=30, help_text='Durée de chaque créneau en minutes (min: 15)', validators=[MinValueValidator(15)])),
                ('repeat_weekly', models.BooleanField(default=False, help_text='Si coché, ce créneau est répété chaque semaine au même jour')),
                ('is_active', models.BooleanField(default=True, help_text='Désactiver temporairement sans supprimer')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('jurist', models.ForeignKey(blank=True, help_text="Juriste concerné (uniquement pour availability_type='specific')", limit_choices_to={'is_staff': True}, null=True, on_delete=django.db.models.deletion.CASCADE, related_name='specific_availabilities', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'verbose_name': 'Disponibilité juriste',
                'verbose_name_plural': 'Disponibilités juristes',
                'ordering': ['date', 'start_time'],
            },
        ),
        migrations.AddIndex(
            model_name='juristglobalavailability',
            index=models.Index(fields=['date', 'availability_type'], name='jurist_avail_date_type_idx'),
        ),
        migrations.AddIndex(
            model_name='juristglobalavailability',
            index=models.Index(fields=['jurist', 'date'], name='jurist_avail_jurist_date_idx'),
        ),
    ]