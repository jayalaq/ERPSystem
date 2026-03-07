"""
n8n Event Dispatcher Service.
Sends events from the ERP to n8n webhooks and processes incoming actions.
"""
import hashlib
import hmac
import json
import logging
from datetime import date, datetime
from decimal import Decimal

import requests
from django.utils import timezone

from .models import N8nWebhook, N8nEventLog, N8nIncomingAction

logger = logging.getLogger(__name__)


class DecimalEncoder(json.JSONEncoder):
    """JSON encoder that handles Decimal and date types."""
    def default(self, obj):
        if isinstance(obj, Decimal):
            return float(obj)
        if isinstance(obj, (datetime, date)):
            return obj.isoformat()
        return super().default(obj)


class N8nEventDispatcher:
    """Dispatches ERP events to registered n8n webhooks."""

    @staticmethod
    def dispatch(event_type, payload):
        """Send event to all active webhooks registered for this event type."""
        webhooks = N8nWebhook.objects.filter(
            event_type=event_type, is_active=True
        )
        for webhook in webhooks:
            log = N8nEventLog.objects.create(
                webhook=webhook,
                event_type=event_type,
                payload=payload,
                status='pending',
            )
            # Send async via Celery
            from .tasks import send_webhook_event
            send_webhook_event.delay(log.pk)
        return webhooks.count()

    @staticmethod
    def send_event(log_id):
        """Actually send the webhook request to n8n."""
        try:
            log = N8nEventLog.objects.select_related('webhook').get(pk=log_id)
            webhook = log.webhook
            log.attempts += 1

            headers = {
                'Content-Type': 'application/json',
                'X-ERP-Event': log.event_type,
                'X-ERP-Timestamp': timezone.now().isoformat(),
            }

            # Add HMAC signature if secret configured
            if webhook.secret_key:
                payload_bytes = json.dumps(log.payload, cls=DecimalEncoder).encode()
                signature = hmac.new(
                    webhook.secret_key.encode(),
                    payload_bytes,
                    hashlib.sha256
                ).hexdigest()
                headers['X-ERP-Signature'] = f"sha256={signature}"

            # Merge custom headers
            if webhook.headers:
                headers.update(webhook.headers)

            response = requests.post(
                webhook.webhook_url,
                json=log.payload,
                headers=headers,
                timeout=webhook.timeout,
            )

            log.response_code = response.status_code
            log.response_body = response.text[:2000]
            log.sent_at = timezone.now()

            if response.status_code in (200, 201, 202, 204):
                log.status = 'sent'
                log.save()
                return True
            else:
                log.status = 'failed'
                log.error_message = f"HTTP {response.status_code}: {response.text[:500]}"
                log.save()
                return False

        except requests.Timeout:
            log.status = 'failed'
            log.error_message = f"Timeout after {webhook.timeout}s"
            log.save()
            return False
        except Exception as e:
            logger.error(f"Error sending n8n event {log_id}: {e}")
            if log:
                log.status = 'failed'
                log.error_message = str(e)[:1000]
                log.save()
            return False


class N8nActionProcessor:
    """Processes incoming actions FROM n8n into the ERP."""

    @staticmethod
    def process(action_type, payload, execution_id=''):
        """Route and execute an action from n8n."""
        log = N8nIncomingAction.objects.create(
            action_type=action_type,
            payload=payload,
            n8n_execution_id=execution_id,
        )

        handlers = {
            'create_customer': N8nActionProcessor._create_customer,
            'update_customer': N8nActionProcessor._update_customer,
            'create_product': N8nActionProcessor._create_product,
            'update_stock': N8nActionProcessor._update_stock,
            'create_invoice': N8nActionProcessor._create_invoice,
            'send_to_sunat': N8nActionProcessor._send_to_sunat,
            'update_opportunity': N8nActionProcessor._update_opportunity,
            'sync_exchange_rate': N8nActionProcessor._sync_exchange_rate,
        }

        handler = handlers.get(action_type)
        if not handler:
            log.error_message = f"Unknown action type: {action_type}"
            log.save()
            return {'success': False, 'error': log.error_message}

        try:
            result = handler(payload)
            log.success = result.get('success', False)
            log.result = result
            if not log.success:
                log.error_message = result.get('error', '')
            log.save()
            return result
        except Exception as e:
            log.error_message = str(e)
            log.save()
            logger.error(f"n8n action {action_type} failed: {e}")
            return {'success': False, 'error': str(e)}

    @staticmethod
    def _create_customer(data):
        from apps.crm.models import Customer
        customer = Customer.objects.create(
            doc_type=data.get('doc_type', 'DNI'),
            doc_number=data['doc_number'],
            name=data['name'],
            customer_type=data.get('customer_type', 'individual'),
            email=data.get('email', ''),
            phone=data.get('phone', ''),
            address=data.get('address', ''),
        )
        N8nEventDispatcher.dispatch('customer.created', {
            'id': customer.pk, 'name': customer.name,
            'doc_number': customer.doc_number, 'source': 'n8n',
        })
        return {'success': True, 'customer_id': customer.pk, 'name': customer.name}

    @staticmethod
    def _update_customer(data):
        from apps.crm.models import Customer
        customer = Customer.objects.get(doc_number=data['doc_number'])
        for field in ['name', 'email', 'phone', 'address', 'credit_limit', 'credit_days']:
            if field in data:
                setattr(customer, field, data[field])
        customer.save()
        return {'success': True, 'customer_id': customer.pk}

    @staticmethod
    def _create_product(data):
        from apps.logistics.models import Product, UnitOfMeasure
        unit = UnitOfMeasure.objects.get(code=data.get('unit_code', 'NIU'))
        product = Product.objects.create(
            sku=data['sku'],
            name=data['name'],
            sale_price=Decimal(str(data.get('sale_price', 0))),
            purchase_price=Decimal(str(data.get('purchase_price', 0))),
            unit=unit,
            product_type=data.get('product_type', 'product'),
        )
        return {'success': True, 'product_id': product.pk, 'sku': product.sku}

    @staticmethod
    def _update_stock(data):
        from apps.logistics.models import Product, Warehouse, StockLevel, StockMovement
        product = Product.objects.get(sku=data['sku'])
        warehouse = Warehouse.objects.get(code=data.get('warehouse_code', 'ALM-001'))
        quantity = Decimal(str(data['quantity']))
        movement_type = data.get('movement_type', 'in')

        stock, _ = StockLevel.objects.get_or_create(
            product=product, warehouse=warehouse, defaults={'quantity': 0}
        )
        if movement_type == 'in':
            stock.quantity += quantity
        elif movement_type == 'out':
            stock.quantity -= quantity
        else:
            stock.quantity = quantity  # adjustment
        stock.save()

        StockMovement.objects.create(
            movement_type=movement_type if movement_type != 'set' else 'adjustment',
            product=product, warehouse=warehouse, quantity=quantity,
            reference=f"n8n-{data.get('reference', '')}",
            reference_type='n8n',
        )

        # Check low stock
        if product.min_stock and stock.quantity <= product.min_stock:
            N8nEventDispatcher.dispatch('stock.low', {
                'product_id': product.pk, 'sku': product.sku,
                'name': product.name, 'current_stock': float(stock.quantity),
                'min_stock': float(product.min_stock),
            })

        return {'success': True, 'product': product.sku, 'new_quantity': float(stock.quantity)}

    @staticmethod
    def _create_invoice(data):
        from apps.accounting.models import Invoice, InvoiceItem, DocumentSeries
        from apps.crm.models import Customer
        from apps.logistics.models import Product

        customer = Customer.objects.get(doc_number=data['customer_doc_number'])
        doc_type = data.get('doc_type', '03')
        series_obj = DocumentSeries.objects.filter(doc_type=doc_type, is_active=True).first()
        if not series_obj:
            return {'success': False, 'error': 'No hay serie de documento configurada'}

        correlative = series_obj.get_next_number()
        invoice = Invoice.objects.create(
            doc_type=doc_type,
            series=series_obj.series,
            correlative=correlative,
            issue_date=data.get('issue_date', timezone.now().date()),
            customer=customer,
            payment_condition=data.get('payment_condition', 'cash'),
            status='draft',
        )

        total_gravada = Decimal('0')
        total_igv = Decimal('0')
        for item_data in data.get('items', []):
            product = Product.objects.get(sku=item_data['sku'])
            qty = Decimal(str(item_data['quantity']))
            price = Decimal(str(item_data.get('unit_price', product.sale_price)))
            subtotal = qty * price
            igv = subtotal * Decimal('0.18') if product.affectation_type == '10' else Decimal('0')

            InvoiceItem.objects.create(
                invoice=invoice, product=product,
                description=product.name, unit=product.unit,
                quantity=qty, unit_price=price,
                subtotal=subtotal, igv=igv, total=subtotal + igv,
                affectation_type=product.affectation_type,
            )
            total_gravada += subtotal
            total_igv += igv

        invoice.op_gravada = total_gravada
        invoice.igv = total_igv
        invoice.total = total_gravada + total_igv
        invoice.save()

        N8nEventDispatcher.dispatch('invoice.created', {
            'invoice_id': invoice.pk, 'number': invoice.full_number,
            'customer': customer.name, 'total': float(invoice.total),
        })

        return {'success': True, 'invoice_id': invoice.pk, 'number': invoice.full_number}

    @staticmethod
    def _send_to_sunat(data):
        from apps.accounting.models import Invoice
        from apps.sunat_integration.services import SunatService

        invoice = Invoice.objects.get(pk=data['invoice_id'])
        service = SunatService()
        result = service.send_invoice(invoice)

        event = 'invoice.sunat_accepted' if result.get('success') else 'invoice.sunat_rejected'
        N8nEventDispatcher.dispatch(event, {
            'invoice_id': invoice.pk, 'number': invoice.full_number,
            'result': result,
        })
        return result

    @staticmethod
    def _update_opportunity(data):
        from apps.crm.models import Opportunity
        opp = Opportunity.objects.get(pk=data['opportunity_id'])
        old_stage = opp.stage
        for field in ['stage', 'priority', 'expected_amount', 'probability', 'lost_reason']:
            if field in data:
                setattr(opp, field, data[field])
        opp.save()

        if opp.stage == 'closed_won' and old_stage != 'closed_won':
            N8nEventDispatcher.dispatch('opportunity.won', {
                'id': opp.pk, 'title': opp.title,
                'customer': opp.customer.name, 'amount': float(opp.expected_amount),
            })
        elif opp.stage == 'closed_lost' and old_stage != 'closed_lost':
            N8nEventDispatcher.dispatch('opportunity.lost', {
                'id': opp.pk, 'title': opp.title,
                'customer': opp.customer.name, 'reason': opp.lost_reason,
            })
        return {'success': True, 'opportunity_id': opp.pk, 'stage': opp.stage}

    @staticmethod
    def _sync_exchange_rate(data):
        from apps.core.models import Currency
        Currency.objects.update_or_create(
            code='USD',
            defaults={
                'name': 'Dólar Americano', 'symbol': '$',
                'exchange_rate': Decimal(str(data.get('rate', 3.75))),
            }
        )
        return {'success': True, 'rate': data.get('rate')}
