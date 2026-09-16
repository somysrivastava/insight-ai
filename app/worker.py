# WHY THIS FILE EXISTS:
# Celery app configuration, separate from any router/service. Task
# modules (app/tasks/*.py) import `celery_app` from here and register
# themselves against it via the `@celery_app.task` decorator; this file
# never imports task modules directly, they're pulled in via `include`
# so there's no circular-import risk between worker.py and the tasks
# that depend on it.

import os

from celery import Celery
from celery.schedules import crontab
from dotenv import load_dotenv

load_dotenv()

REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")

celery_app = Celery(
    "insightai",
    broker=REDIS_URL,
    backend=REDIS_URL,
    include=[
        "app.tasks.ai_tasks",
        "app.tasks.analytics_tasks",
        "app.tasks.join_tasks",
        "app.tasks.export_tasks",
        "app.tasks.scheduled_tasks",
        "app.tasks.alert_tasks",
        "app.tasks.dashboard_tasks",
    ],
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    # Results expire from Redis after 1 hour — matches the job-ownership
    # record TTL in app/services/job_service.py, so a job's status and
    # who's allowed to read it expire together.
    result_expires=3600,
    timezone="UTC",
    enable_utc=True,
)

# Day 19 — Beat only ever knows about these two static entries. Which
# ScheduledReport rows exist and when each is actually due lives in the
# database, not here; poll_due_reports_task figures that out itself
# every time it runs. See app/tasks/scheduled_tasks.py.
celery_app.conf.beat_schedule = {
    "poll-scheduled-reports": {
        "task": "scheduled_tasks.poll_due_reports",
        "schedule": crontab(minute="*"),
    },
    "cleanup-expired-exports": {
        "task": "scheduled_tasks.cleanup_expired_exports",
        "schedule": crontab(hour=3, minute=0),
    },
    # Day 20 — daily-frequency alert rules.
    "daily-alert-sweep": {
        "task": "alert_tasks.daily_alert_sweep",
        "schedule": crontab(hour=7, minute=0),
    },
    # Day 21 — refreshes every pin on every active dashboard.
    "daily-dashboard-refresh": {
        "task": "dashboard_tasks.daily_dashboard_refresh",
        "schedule": crontab(hour=6, minute=0),
    },
}
