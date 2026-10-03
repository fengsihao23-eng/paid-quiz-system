from celery import shared_task
from .scoring import generate_result as generate_sync

@shared_task(autoretry_for=(Exception,), retry_backoff=True, max_retries=5)
def generate_result(attempt_id):
    # Optional recovery task. Normal submission creates the result in the same DB transaction.
    generate_sync(attempt_id)
