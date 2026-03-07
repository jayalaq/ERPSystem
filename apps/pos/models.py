from django.db import models
from django.conf import settings
import uuid


class CashRegister(models.Model):
    """Physical cash register/terminal."""
    name = models.CharField(max_length=100, verbose_name='Nombre')
    code = models.CharField(max_length=20, unique=True, verbose_name='Código')
    branch = models.ForeignKey('core.Branch', on_delete=models.CASCADE, related_name='cash_registers')
    is_active = models.BooleanField(default=True)
    printer_name = models.CharField(max_length=100, blank=True, verbose_name='Impresora')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Caja Registradora'
        verbose_name_plural = 'Cajas Registradoras'

    def __str__(self):
        return f"{self.name} ({self.code})"


class CashSession(models.Model):
    """Cash register session (opening and closing)."""

    class Status(models.TextChoices):
        OPEN = 'open', 'Abierta'
        CLOSED = 'closed', 'Cerrada'

    cash_register = models.ForeignKey(CashRegister, on_delete=models.CASCADE, related_name='sessions')
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='cash_sessions')
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.OPEN)
    opening_amount = models.DecimalField(max_digits=12, decimal_places=2, verbose_name='Monto de Apertura')
    closing_amount = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True, verbose_name='Monto de Cierre')
    expected_amount = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True, verbose_name='Monto Esperado')
    difference = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True, verbose_name='Diferencia')
    total_sales = models.DecimalField(max_digits=12, decimal_places=2, default=0, verbose_name='Total Ventas')
    total_cash = models.DecimalField(max_digits=12, decimal_places=2, default=0, verbose_name='Total Efectivo')
    total_card = models.DecimalField(max_digits=12, decimal_places=2, default=0, verbose_name='Total Tarjeta')
    total_transfer = models.DecimalField(max_digits=12, decimal_places=2, default=0, verbose_name='Total Transferencia')
    notes = models.TextField(blank=True, verbose_name='Observaciones')
    opened_at = models.DateTimeField(auto_now_add=True, verbose_name='Apertura')
    closed_at = models.DateTimeField(null=True, blank=True, verbose_name='Cierre')

    class Meta:
        verbose_name = 'Sesión de Caja'
        verbose_name_plural = 'Sesiones de Caja'
        ordering = ['-opened_at']

    def __str__(self):
        return f"Sesión {self.id} - {self.cash_register.name}"


class POSSale(models.Model):
    """Point of sale transaction."""

    class PaymentMethod(models.TextChoices):
        CASH = 'cash', 'Efectivo'
        CARD = 'card', 'Tarjeta'
        TRANSFER = 'transfer', 'Transferencia'
        YAPE = 'yape', 'Yape'
        PLIN = 'plin', 'Plin'
        CREDIT = 'credit', 'Crédito'
        MIXED = 'mixed', 'Mixto'

    class DocType(models.TextChoices):
        BOLETA = 'boleta', 'Boleta de Venta'
        FACTURA = 'factura', 'Factura'
        NOTA_VENTA = 'nota_venta', 'Nota de Venta'
        TICKET = 'ticket', 'Ticket'

    class Status(models.TextChoices):
        COMPLETED = 'completed', 'Completada'
        CANCELLED = 'cancelled', 'Anulada'
        REFUNDED = 'refunded', 'Devuelta'

    uuid = models.UUIDField(default=uuid.uuid4, editable=False, unique=True)
    session = models.ForeignKey(CashSession, on_delete=models.CASCADE, related_name='sales')
    customer = models.ForeignKey('crm.Customer', on_delete=models.SET_NULL, null=True, blank=True, related_name='pos_sales')
    doc_type = models.CharField(max_length=20, choices=DocType.choices, default=DocType.BOLETA)
    series = models.CharField(max_length=10, verbose_name='Serie')
    correlative = models.CharField(max_length=20, verbose_name='Correlativo')
    payment_method = models.CharField(max_length=20, choices=PaymentMethod.choices, default=PaymentMethod.CASH)
    subtotal = models.DecimalField(max_digits=12, decimal_places=2, verbose_name='Subtotal')
    discount = models.DecimalField(max_digits=12, decimal_places=2, default=0, verbose_name='Descuento')
    igv = models.DecimalField(max_digits=12, decimal_places=2, verbose_name='IGV')
    total = models.DecimalField(max_digits=12, decimal_places=2, verbose_name='Total')
    amount_received = models.DecimalField(max_digits=12, decimal_places=2, default=0, verbose_name='Monto Recibido')
    change_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0, verbose_name='Vuelto')
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.COMPLETED)
    sunat_status = models.CharField(max_length=50, blank=True, verbose_name='Estado SUNAT')
    sunat_response = models.JSONField(default=dict, blank=True)
    notes = models.TextField(blank=True)
    seller = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, related_name='pos_sales')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Venta POS'
        verbose_name_plural = 'Ventas POS'
        ordering = ['-created_at']
        unique_together = ['series', 'correlative', 'doc_type']

    def __str__(self):
        return f"{self.series}-{self.correlative}"


class POSSaleItem(models.Model):
    """Individual item in a POS sale."""
    sale = models.ForeignKey(POSSale, on_delete=models.CASCADE, related_name='items')
    product = models.ForeignKey('logistics.Product', on_delete=models.PROTECT, related_name='pos_sale_items')
    quantity = models.DecimalField(max_digits=12, decimal_places=3, verbose_name='Cantidad')
    unit_price = models.DecimalField(max_digits=12, decimal_places=2, verbose_name='Precio Unitario')
    discount = models.DecimalField(max_digits=12, decimal_places=2, default=0, verbose_name='Descuento')
    subtotal = models.DecimalField(max_digits=12, decimal_places=2, verbose_name='Subtotal')
    igv = models.DecimalField(max_digits=12, decimal_places=2, verbose_name='IGV')
    total = models.DecimalField(max_digits=12, decimal_places=2, verbose_name='Total')

    class Meta:
        verbose_name = 'Ítem de Venta'
        verbose_name_plural = 'Ítems de Venta'

    def __str__(self):
        return f"{self.product.name} x {self.quantity}"


class PaymentDetail(models.Model):
    """Payment details for mixed payments."""
    sale = models.ForeignKey(POSSale, on_delete=models.CASCADE, related_name='payment_details')
    method = models.CharField(max_length=20, choices=POSSale.PaymentMethod.choices)
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    reference = models.CharField(max_length=100, blank=True, verbose_name='Referencia')

    class Meta:
        verbose_name = 'Detalle de Pago'
        verbose_name_plural = 'Detalles de Pago'
