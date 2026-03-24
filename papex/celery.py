import os
import ssl
from celery import Celery
from celery.signals import worker_process_init
from django.conf import settings
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "papex.settings.prod")

# Set the default Django settings module for the 'celery' program.
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'papex.settings')

app = Celery('papex')

# Using a string here means the worker doesn't have to serialize
# the configuration object to child processes.
app.config_from_object('django.conf:settings', namespace='CELERY')

# Load task modules from all registered Django apps.
app.autodiscover_tasks()

# Configuration SSL pour Redis si nécessaire
if settings.IS_REDIS_SSL:
    app.conf.broker_transport_options = {
        'ssl': {
            'ssl_cert_reqs': ssl.CERT_NONE
        }
    }

@worker_process_init.connect
def init_worker(**kwargs):
    """
    Initialisation du worker : s'assure que les connexions DB sont prêtes
    """
    import django
    django.setup()