"""
Django signals that automatically trigger n8n webhooks
when ERP events occur across all modules.
"""
from django.db.models.signals import post_save, pre_save
from django.dispatch import receiver

from .services import N8nEventDispatcher


# ============================================
# POS SIGNALS
# ============================================
@receiver(post_save, sender='pos.POSSale')
def on_pos_sale_saved(sender, instance, created, **kwargs):
    if created:
        N8nEventDispatcher.dispatch('sale.completed', {
            'sale_id': instance.pk,
            'uuid': str(instance.uuid),
            'number': f"{instance.series}-{instance.correlative}",
            'doc_type': instance.doc_type,
            'customer': instance.customer.name if instance.customer else 'Varios',
            'customer_doc': instance.customer.doc_number if instance.customer else '',
            'payment_method': instance.payment_method,
            'subtotal': float(instance.subtotal),
            'igv': float(instance.igv),
            'discount': float(instance.discount),
            'total': float(instance.total),
            'seller': instance.seller.get_full_name() if instance.seller else '',
            'items': list(instance.items.values(
                'product__name', 'product__sku', 'quantity', 'unit_price', 'total'
            )),
        })


@receiver(pre_save, sender='pos.POSSale')
def on_pos_sale_cancelled(sender, instance, **kwargs):
    if instance.pk:
        try:
            old = sender.objects.get(pk=instance.pk)
            if old.status != 'cancelled' and instance.status == 'cancelled':
                N8nEventDispatcher.dispatch('sale.cancelled', {
                    'sale_id': instance.pk,
                    'number': f"{instance.series}-{instance.correlative}",
                    'total': float(instance.total),
                })
        except sender.DoesNotExist:
            pass


@receiver(post_save, sender='pos.CashSession')
def on_cash_session_saved(sender, instance, created, **kwargs):
    if created:
        N8nEventDispatcher.dispatch('session.opened', {
            'session_id': instance.pk,
            'register': instance.cash_register.name,
            'user': instance.user.get_full_name(),
            'opening_amount': float(instance.opening_amount),
        })
    elif instance.status == 'closed':
        N8nEventDispatcher.dispatch('session.closed', {
            'session_id': instance.pk,
            'register': instance.cash_register.name,
            'user': instance.user.get_full_name(),
            'total_sales': float(instance.total_sales),
            'total_cash': float(instance.total_cash),
            'total_card': float(instance.total_card),
            'difference': float(instance.difference) if instance.difference else 0,
        })


# ============================================
# CRM SIGNALS
# ============================================
@receiver(post_save, sender='crm.Customer')
def on_customer_saved(sender, instance, created, **kwargs):
    event = 'customer.created' if created else 'customer.updated'
    N8nEventDispatcher.dispatch(event, {
        'customer_id': instance.pk,
        'doc_type': instance.doc_type,
        'doc_number': instance.doc_number,
        'name': instance.name,
        'customer_type': instance.customer_type,
        'email': instance.email,
        'phone': instance.phone,
        'credit_limit': float(instance.credit_limit),
    })


@receiver(post_save, sender='crm.Opportunity')
def on_opportunity_saved(sender, instance, created, **kwargs):
    if created:
        N8nEventDispatcher.dispatch('opportunity.created', {
            'opportunity_id': instance.pk,
            'title': instance.title,
            'customer': instance.customer.name,
            'stage': instance.stage,
            'expected_amount': float(instance.expected_amount),
            'probability': instance.probability,
            'assigned_to': instance.assigned_to.get_full_name() if instance.assigned_to else '',
        })


@receiver(post_save, sender='crm.Interaction')
def on_interaction_saved(sender, instance, created, **kwargs):
    if created:
        N8nEventDispatcher.dispatch('interaction.created', {
            'interaction_id': instance.pk,
            'customer': instance.customer.name,
            'type': instance.interaction_type,
            'subject': instance.subject,
            'description': instance.description,
            'next_action': instance.next_action,
            'performed_by': instance.performed_by.get_full_name() if instance.performed_by else '',
        })


# ============================================
# LOGISTICS SIGNALS
# ============================================
@receiver(post_save, sender='logistics.StockMovement')
def on_stock_movement(sender, instance, created, **kwargs):
    if created:
        N8nEventDispatcher.dispatch('stock.movement', {
            'movement_id': instance.pk,
            'type': instance.movement_type,
            'product': instance.product.name,
            'sku': instance.product.sku,
            'warehouse': instance.warehouse.name,
            'quantity': float(instance.quantity),
            'reference': instance.reference,
        })


@receiver(post_save, sender='logistics.Product')
def on_product_saved(sender, instance, created, **kwargs):
    if created:
        N8nEventDispatcher.dispatch('product.created', {
            'product_id': instance.pk,
            'sku': instance.sku,
            'name': instance.name,
            'sale_price': float(instance.sale_price),
            'purchase_price': float(instance.purchase_price),
            'category': instance.category.name if instance.category else '',
        })


@receiver(post_save, sender='logistics.PurchaseOrder')
def on_purchase_order_saved(sender, instance, created, **kwargs):
    if created:
        N8nEventDispatcher.dispatch('purchase.created', {
            'order_id': instance.pk,
            'number': instance.number,
            'supplier': instance.supplier.name,
            'total': float(instance.total),
            'expected_date': instance.expected_date.isoformat() if instance.expected_date else '',
        })
    elif instance.status == 'received':
        N8nEventDispatcher.dispatch('purchase.received', {
            'order_id': instance.pk,
            'number': instance.number,
            'supplier': instance.supplier.name,
            'total': float(instance.total),
        })


# ============================================
# ACCOUNTING SIGNALS
# ============================================
@receiver(post_save, sender='accounting.Invoice')
def on_invoice_saved(sender, instance, created, **kwargs):
    if created:
        N8nEventDispatcher.dispatch('invoice.created', {
            'invoice_id': instance.pk,
            'number': instance.full_number,
            'doc_type': instance.get_doc_type_display(),
            'customer': instance.customer.name,
            'total': float(instance.total),
            'igv': float(instance.igv),
            'status': instance.status,
        })


@receiver(pre_save, sender='accounting.Invoice')
def on_invoice_sunat_status_changed(sender, instance, **kwargs):
    if instance.pk:
        try:
            old = sender.objects.get(pk=instance.pk)
            if old.status != instance.status:
                if instance.status == 'accepted':
                    N8nEventDispatcher.dispatch('invoice.sunat_accepted', {
                        'invoice_id': instance.pk,
                        'number': instance.full_number,
                        'total': float(instance.total),
                        'response_code': instance.sunat_response_code,
                    })
                elif instance.status == 'rejected':
                    N8nEventDispatcher.dispatch('invoice.sunat_rejected', {
                        'invoice_id': instance.pk,
                        'number': instance.full_number,
                        'response': instance.sunat_response_description,
                    })
        except sender.DoesNotExist:
            pass


@receiver(post_save, sender='accounting.PaymentRecord')
def on_payment_received(sender, instance, created, **kwargs):
    if created:
        N8nEventDispatcher.dispatch('payment.received', {
            'payment_id': instance.pk,
            'invoice': instance.invoice.full_number,
            'amount': float(instance.amount),
            'method': instance.payment_method,
            'customer': instance.invoice.customer.name,
        })
