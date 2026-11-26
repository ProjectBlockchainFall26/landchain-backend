"""Celery app (task B1). Queues: default, signer.registrar, signer.id_officer, signer.admin (concurrency 1 each).

    celery -A config worker -l info -Q default
    celery -A config worker -l info -Q signer.registrar,signer.id_officer,signer.admin --concurrency 1
    celery -A config beat -l info

Beat schedule (spec section 13) is in settings.CELERY_BEAT_SCHEDULE.
"""
import os

from celery import Celery

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")

app = Celery("landchain")
app.config_from_object("django.conf:settings", namespace="CELERY")
app.autodiscover_tasks()
