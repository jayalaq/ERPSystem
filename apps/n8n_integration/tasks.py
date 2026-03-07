"""Celery tasks for n8n webhook delivery."""
import logging
from celery import shared_task
from django.db.models import Sum, Count
from django.utils import timezone
from decimal import Decimal

logger = logging.getLogger(__name__)


@shared_task(bind=True, max_retries=3, default_retry_delay=10, queue='n8n_events')
def send_webhook_event(self, log_id):
    """Send a single webhook event to n8n with retries."""
    from .services import N8nEventDispatcher

    success = N8nEventDispatcher.send_event(log_id)
    if not success:
        from .models import N8nEventLog
        log = N8nEventLog.objects.get(pk=log_id)
        if log.attempts < log.webhook.retry_count:
            log.status = 'retrying'
            log.save()
            raise self.retry(countdown=10 * log.attempts)
    return success


@shared_task
def send_daily_summary():
    """Send daily business summary to n8n at end of day."""
    from apps.pos.models import POSSale
    from apps.crm.models import Customer, Opportunity
    from apps.accounting.models import Invoice
    from .services import N8nEventDispatcher

    today = timezone.now().date()

    sales = POSSale.objects.filter(
        created_at__date=today, status='completed'
    ).aggregate(
        count=Count('id'),
        total=Sum('total'),
        cash=Sum('total', filter=__import__('django.db.models', fromlist=['Q']).Q(payment_method='cash')),
        card=Sum('total', filter=__import__('django.db.models', fromlist=['Q']).Q(payment_method='card')),
    )

    new_customers = Customer.objects.filter(created_at__date=today).count()
    new_opportunities = Opportunity.objects.filter(created_at__date=today).count()
    invoices_sent = Invoice.objects.filter(
        created_at__date=today, status='accepted'
    ).count()

    payload = {
        'date': today.isoformat(),
        'sales': {
            'count': sales['count'] or 0,
            'total': float(sales['total'] or 0),
            'cash': float(sales['cash'] or 0),
            'card': float(sales['card'] or 0),
        },
        'crm': {
            'new_customers': new_customers,
            'new_opportunities': new_opportunities,
        },
        'sunat': {
            'invoices_sent': invoices_sent,
        },
    }

    N8nEventDispatcher.dispatch('system.daily_summary', payload)
    return payload


@shared_task
def retry_failed_webhooks():
    """Retry all failed webhook deliveries from the last 24 hours."""
    from .models import N8nEventLog
    cutoff = timezone.now() - timezone.timedelta(hours=24)
    failed = N8nEventLog.objects.filter(
        status='failed',
        created_at__gte=cutoff,
        attempts__lt=__import__('django.db.models', fromlist=['F']).F('webhook__retry_count'),
    )
    for log in failed:
        log.status = 'retrying'
        log.save()
        send_webhook_event.delay(log.pk)
    return f"Retrying {failed.count()} failed webhooks"
