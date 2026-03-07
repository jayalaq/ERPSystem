import logging
from celery import shared_task
from django.utils import timezone

logger = logging.getLogger(__name__)


@shared_task
def check_overdue_invoices():
    """Mark overdue accounts payable."""
    from .models import AccountPayable
    today = timezone.now().date()
    updated = AccountPayable.objects.filter(
        status='pending', due_date__lt=today
    ).update(status='overdue')
    logger.info(f"Marked {updated} accounts payable as overdue")
    return f"Updated {updated} overdue payables"


@shared_task
def generate_monthly_report(year, month):
    """Generate monthly sales report."""
    from apps.pos.models import POSSale
    from django.db.models import Sum, Count

    sales = POSSale.objects.filter(
        created_at__year=year,
        created_at__month=month,
        status='completed'
    ).aggregate(
        total_sales=Sum('total'),
        total_count=Count('id'),
        total_igv=Sum('igv'),
    )
    logger.info(f"Monthly report {year}-{month}: {sales}")
    return sales
