import logging
from celery import shared_task

logger = logging.getLogger(__name__)


@shared_task(bind=True, max_retries=3, default_retry_delay=60)
def send_invoice_to_sunat(self, invoice_id):
    """Send invoice to SUNAT asynchronously."""
    from apps.accounting.models import Invoice
    from .services import SunatService

    try:
        invoice = Invoice.objects.get(pk=invoice_id)
        service = SunatService()
        result = service.send_invoice(invoice)
        logger.info(f"SUNAT invoice {invoice.full_number}: {result}")
        return result
    except Exception as exc:
        logger.error(f"Error sending invoice {invoice_id} to SUNAT: {exc}")
        raise self.retry(exc=exc)


@shared_task
def update_exchange_rate():
    """Update exchange rate from SUNAT."""
    from apps.core.models import Currency
    from .services import SunatService

    service = SunatService()
    result = service.get_exchange_rate()
    if result['success']:
        data = result['data']
        Currency.objects.update_or_create(
            code='USD',
            defaults={
                'name': 'Dólar Americano',
                'symbol': '$',
                'exchange_rate': data.get('venta', 3.75),
            }
        )
        logger.info(f"Exchange rate updated: {data}")
    return result


@shared_task
def bulk_send_pending_invoices():
    """Send all pending invoices to SUNAT."""
    from apps.accounting.models import Invoice
    pending = Invoice.objects.filter(status='issued')
    for invoice in pending:
        send_invoice_to_sunat.delay(invoice.pk)
    return f"Queued {pending.count()} invoices"
