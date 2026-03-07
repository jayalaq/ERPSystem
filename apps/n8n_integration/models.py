from django.db import models
from django.conf import settings


class N8nWebhook(models.Model):
    """Registered n8n webhooks that the ERP triggers."""

    class EventType(models.TextChoices):
        # POS Events
        SALE_COMPLETED = 'sale.completed', 'Venta Completada'
        SALE_CANCELLED = 'sale.cancelled', 'Venta Anulada'
        SESSION_OPENED = 'session.opened', 'Caja Abierta'
        SESSION_CLOSED = 'session.closed', 'Caja Cerrada'
        # CRM Events
        CUSTOMER_CREATED = 'customer.created', 'Cliente Creado'
        CUSTOMER_UPDATED = 'customer.updated', 'Cliente Actualizado'
        OPPORTUNITY_CREATED = 'opportunity.created', 'Oportunidad Creada'
        OPPORTUNITY_WON = 'opportunity.won', 'Oportunidad Ganada'
        OPPORTUNITY_LOST = 'opportunity.lost', 'Oportunidad Perdida'
        INTERACTION_CREATED = 'interaction.created', 'Interacción Registrada'
        # Logistics Events
        STOCK_LOW = 'stock.low', 'Stock Bajo'
        STOCK_MOVEMENT = 'stock.movement', 'Movimiento de Stock'
        PURCHASE_ORDER_CREATED = 'purchase.created', 'Orden de Compra Creada'
        PURCHASE_ORDER_RECEIVED = 'purchase.received', 'Orden de Compra Recibida'
        PRODUCT_CREATED = 'product.created', 'Producto Creado'
        # Accounting Events
        INVOICE_CREATED = 'invoice.created', 'Comprobante Creado'
        INVOICE_SUNAT_ACCEPTED = 'invoice.sunat_accepted', 'Comprobante Aceptado SUNAT'
        INVOICE_SUNAT_REJECTED = 'invoice.sunat_rejected', 'Comprobante Rechazado SUNAT'
        PAYMENT_RECEIVED = 'payment.received', 'Pago Recibido'
        PAYMENT_OVERDUE = 'payment.overdue', 'Pago Vencido'
        # System Events
        DAILY_SUMMARY = 'system.daily_summary', 'Resumen Diario'
        BACKUP_COMPLETED = 'system.backup', 'Backup Completado'

    name = models.CharField(max_length=200, verbose_name='Nombre')
    event_type = models.CharField(max_length=50, choices=EventType.choices, verbose_name='Evento')
    webhook_url = models.URLField(verbose_name='URL del Webhook n8n')
    is_active = models.BooleanField(default=True, verbose_name='Activo')
    secret_key = models.CharField(max_length=100, blank=True, verbose_name='Clave Secreta',
                                  help_text='Para verificar autenticidad del webhook')
    headers = models.JSONField(default=dict, blank=True, verbose_name='Headers adicionales')
    retry_count = models.PositiveIntegerField(default=3, verbose_name='Reintentos')
    timeout = models.PositiveIntegerField(default=30, verbose_name='Timeout (seg)')
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Webhook n8n'
        verbose_name_plural = 'Webhooks n8n'
        ordering = ['event_type', 'name']

    def __str__(self):
        return f"{self.name} ({self.get_event_type_display()})"


class N8nEventLog(models.Model):
    """Log of events sent to n8n."""

    class Status(models.TextChoices):
        PENDING = 'pending', 'Pendiente'
        SENT = 'sent', 'Enviado'
        FAILED = 'failed', 'Fallido'
        RETRYING = 'retrying', 'Reintentando'

    webhook = models.ForeignKey(N8nWebhook, on_delete=models.CASCADE, related_name='logs')
    event_type = models.CharField(max_length=50)
    payload = models.JSONField(default=dict)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.PENDING)
    response_code = models.IntegerField(null=True, blank=True)
    response_body = models.TextField(blank=True)
    error_message = models.TextField(blank=True)
    attempts = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    sent_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        verbose_name = 'Log de Evento n8n'
        verbose_name_plural = 'Logs de Eventos n8n'
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.event_type} → {self.status} ({self.created_at:%d/%m %H:%M})"


class N8nIncomingAction(models.Model):
    """Log of actions received FROM n8n into the ERP."""

    class ActionType(models.TextChoices):
        CREATE_CUSTOMER = 'create_customer', 'Crear Cliente'
        UPDATE_CUSTOMER = 'update_customer', 'Actualizar Cliente'
        CREATE_PRODUCT = 'create_product', 'Crear Producto'
        UPDATE_STOCK = 'update_stock', 'Actualizar Stock'
        CREATE_INVOICE = 'create_invoice', 'Crear Comprobante'
        CREATE_SALE = 'create_sale', 'Crear Venta'
        SEND_TO_SUNAT = 'send_to_sunat', 'Enviar a SUNAT'
        UPDATE_OPPORTUNITY = 'update_opportunity', 'Actualizar Oportunidad'
        SYNC_EXCHANGE_RATE = 'sync_exchange_rate', 'Sincronizar Tipo Cambio'

    action_type = models.CharField(max_length=50, choices=ActionType.choices)
    source = models.CharField(max_length=100, default='n8n', verbose_name='Origen')
    payload = models.JSONField(default=dict)
    result = models.JSONField(default=dict, blank=True)
    success = models.BooleanField(default=False)
    error_message = models.TextField(blank=True)
    n8n_execution_id = models.CharField(max_length=100, blank=True, verbose_name='n8n Execution ID')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Acción Entrante n8n'
        verbose_name_plural = 'Acciones Entrantes n8n'
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.get_action_type_display()} - {'OK' if self.success else 'Error'}"
