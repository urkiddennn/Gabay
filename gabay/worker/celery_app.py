from celery import Celery
import os

# Default to the docker-compose redis service name if not set
redis_url = os.environ.get("REDIS_URL", "redis://localhost:6379/0")

celery_app = Celery(
    "gabay_worker",
    broker=redis_url,
    backend=redis_url,
    include=["gabay.worker.tasks"]
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    beat_schedule={
        "check-reminders-every-minute": {
            "task": "worker.tasks.check_reminders",
            "schedule": 60.0,
        },
        "proactive-heartbeat-every-15-minutes": {
            "task": "worker.tasks.proactive_heartbeat",
            "schedule": 900.0, # 15 minutes
        },
    },
)
