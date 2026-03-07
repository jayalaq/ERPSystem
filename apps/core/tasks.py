import logging
from celery import shared_task

logger = logging.getLogger(__name__)


@shared_task
def send_backup_reminder():
    """Send weekly backup reminder."""
    logger.info("Weekly backup reminder: Ensure database backups are current.")
    return "Backup reminder sent"
