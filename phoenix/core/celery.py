import os

from celery import Celery

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'phoenix.core.settings')

app = Celery('phoenix')
app.config_from_object('django.conf:settings', namespace='CELERY')
app.autodiscover_tasks()
app.conf.broker_transport_options = {
    'max_retries': 5,
    'interval_start': 0,
    'interval_step': 0.2,
    'interval_max': 0.2,
}
