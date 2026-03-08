from django.db import models
from django.conf import settings
from django.utils import timezone
from decimal import Decimal


class SalesQuotation(models.Model):
    """Cotizacion de Venta - Sales Quotation."""

    class Status(models.TextChoices):
        DRAFT = 'draft', 'Borrador'
        SENT = 'sent', 'Enviada'
        ACCEPTED = 'accepted', 'Aceptada'
        REJECTED = 'rejected', 'Rechazada'
        EXPIRED = 'expired', 'Expirada'
        CANCELLED = 'cancelled', 'Cancelada'

    number = models.CharField(max_length=20, unique=True, verbose_name='Numero')
    customer = models.ForeignKey(
        'crm.Customer', on_delete=models.PROTECT, related_name='quotations', verbose_name='Cliente'
    )
    contact_name = models.CharField(max_length=200, blank=True, verbose_name='Contacto')
    contact_email = models.EmailField(blank=True, verbose_name='Email')
    contact_phone = models.CharField(max_length=20, blank=True, verbose_name='Telefono')

    status = models.CharField(max_length=20, choices=Status.choices, default=Status.DRAFT)
    issue_date = models.DateField(verbose_name='Fecha de Emision')
    valid_until = models.DateField(verbose_name='Valida Hasta')

    # Payment terms
    payment_terms = models.CharField(max_length=200, blank=True, verbose_name='Condiciones de Pago',
                                     default='Contado')
    delivery_terms = models.CharField(max_length=200, blank=True, verbose_name='Condiciones de Entrega')
    delivery_time = models.CharField(max_length=100, blank=True, verbose_name='Tiempo de Entrega')

    # Amounts
    subtotal = models.DecimalField(max_digits=12, decimal_places=2, default=0, verbose_name='Subtotal')
    discount_percent = models.DecimalField(max_digits=5, decimal_places=2, default=0, verbose_name='% Descuento')
    discount_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0, verbose_name='Descuento')
    igv = models.DecimalField(max_digits=12, decimal_places=2, default=0, verbose_name='IGV')
    total = models.DecimalField(max_digits=12, decimal_places=2, default=0, verbose_name='Total')

    notes = models.TextField(blank=True, verbose_name='Notas')
    internal_notes = models.TextField(blank=True, verbose_name='Notas Internas')

    # Tracking
    sales_order = models.OneToOneField(
        'SalesOrder', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='quotation', verbose_name='Pedido Generado'
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, related_name='quotations_created'
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Cotizacion'
        verbose_name_plural = 'Cotizaciones'
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.number} - {self.customer.name}"

    @property
    def is_expired(self):
        return self.valid_until < timezone.now().date() and self.status not in ('accepted', 'cancelled')

    def recalculate_totals(self):
        """Recalculate totals from items."""
        items = self.items.all()
        self.subtotal = sum(item.subtotal for item in items)
        if self.discount_percent > 0:
            self.discount_amount = self.subtotal * self.discount_percent / Decimal('100')
        base_imponible = self.subtotal - self.discount_amount
        # Calculate IGV based on item affectation types
        self.igv = sum(item.igv for item in items)
        if self.discount_percent > 0:
            self.igv = base_imponible * Decimal('0.18')
        self.total = base_imponible + self.igv
        self.save(update_fields=['subtotal', 'discount_amount', 'igv', 'total'])


class SalesQuotationItem(models.Model):
    """Items in a sales quotation."""
    quotation = models.ForeignKey(SalesQuotation, on_delete=models.CASCADE, related_name='items')
    product = models.ForeignKey(
        'logistics.Product', on_delete=models.PROTECT, related_name='quotation_items', verbose_name='Producto'
    )
    description = models.CharField(max_length=500, verbose_name='Descripcion')
    quantity = models.DecimalField(max_digits=12, decimal_places=3, verbose_name='Cantidad')
    unit = models.ForeignKey(
        'logistics.UnitOfMeasure', on_delete=models.PROTECT, verbose_name='Unidad'
    )
    unit_price = models.DecimalField(max_digits=12, decimal_places=2, verbose_name='Precio Unitario')
    discount = models.DecimalField(max_digits=12, decimal_places=2, default=0, verbose_name='Descuento')
    affectation_type = models.CharField(max_length=2, default='10', verbose_name='Tipo Afectacion')
    igv = models.DecimalField(max_digits=12, decimal_places=2, default=0, verbose_name='IGV')
    subtotal = models.DecimalField(max_digits=12, decimal_places=2, default=0, verbose_name='Subtotal')
    total = models.DecimalField(max_digits=12, decimal_places=2, default=0, verbose_name='Total')

    class Meta:
        verbose_name = 'Item de Cotizacion'
        verbose_name_plural = 'Items de Cotizacion'

    def __str__(self):
        return f"{self.description} x {self.quantity}"

    def calculate_totals(self):
        """Calculate line item totals."""
        self.subtotal = (self.quantity * self.unit_price) - self.discount
        if self.affectation_type == '10':  # Gravado
            self.igv = self.subtotal * Decimal('0.18')
        else:
            self.igv = Decimal('0')
        self.total = self.subtotal + self.igv


class SalesOrder(models.Model):
    """Pedido de Venta - Sales Order (B2B)."""

    class Status(models.TextChoices):
        DRAFT = 'draft', 'Borrador'
        CONFIRMED = 'confirmed', 'Confirmado'
        IN_PROCESS = 'in_process', 'En Preparacion'
        READY = 'ready', 'Listo para Despacho'
        DISPATCHED = 'dispatched', 'Despachado'
        DELIVERED = 'delivered', 'Entregado'
        INVOICED = 'invoiced', 'Facturado'
        CANCELLED = 'cancelled', 'Cancelado'

    class Priority(models.TextChoices):
        LOW = 'low', 'Baja'
        NORMAL = 'normal', 'Normal'
        HIGH = 'high', 'Alta'
        URGENT = 'urgent', 'Urgente'

    number = models.CharField(max_length=20, unique=True, verbose_name='Numero')
    customer = models.ForeignKey(
        'crm.Customer', on_delete=models.PROTECT, related_name='sales_orders', verbose_name='Cliente'
    )
    warehouse = models.ForeignKey(
        'logistics.Warehouse', on_delete=models.PROTECT, related_name='sales_orders', verbose_name='Almacen'
    )

    status = models.CharField(max_length=20, choices=Status.choices, default=Status.DRAFT)
    priority = models.CharField(max_length=10, choices=Priority.choices, default=Priority.NORMAL, verbose_name='Prioridad')

    order_date = models.DateField(verbose_name='Fecha de Pedido')
    expected_date = models.DateField(null=True, blank=True, verbose_name='Fecha Esperada de Entrega')
    delivery_date = models.DateField(null=True, blank=True, verbose_name='Fecha Real de Entrega')

    # Delivery info
    delivery_address = models.TextField(blank=True, verbose_name='Direccion de Entrega')

    # Payment
    payment_terms = models.CharField(max_length=200, blank=True, verbose_name='Condiciones de Pago')

    # Amounts
    subtotal = models.DecimalField(max_digits=12, decimal_places=2, default=0, verbose_name='Subtotal')
    discount_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0, verbose_name='Descuento')
    igv = models.DecimalField(max_digits=12, decimal_places=2, default=0, verbose_name='IGV')
    total = models.DecimalField(max_digits=12, decimal_places=2, default=0, verbose_name='Total')

    notes = models.TextField(blank=True, verbose_name='Notas')
    internal_notes = models.TextField(blank=True, verbose_name='Notas Internas')

    # Related documents
    invoice = models.ForeignKey(
        'accounting.Invoice', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='sales_orders', verbose_name='Comprobante'
    )
    dispatch_guide = models.ForeignKey(
        'logistics.DispatchGuide', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='sales_orders', verbose_name='Guia de Remision'
    )

    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, related_name='sales_orders_created'
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Pedido de Venta'
        verbose_name_plural = 'Pedidos de Venta'
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.number} - {self.customer.name}"

    def recalculate_totals(self):
        """Recalculate totals from items."""
        items = self.items.all()
        self.subtotal = sum(item.subtotal for item in items)
        self.igv = sum(item.igv for item in items)
        self.total = self.subtotal + self.igv - self.discount_amount
        self.save(update_fields=['subtotal', 'igv', 'total'])

    @property
    def can_confirm(self):
        return self.status == 'draft' and self.items.exists()

    @property
    def can_dispatch(self):
        return self.status in ('confirmed', 'in_process', 'ready')


class SalesOrderItem(models.Model):
    """Items in a sales order."""
    order = models.ForeignKey(SalesOrder, on_delete=models.CASCADE, related_name='items')
    product = models.ForeignKey(
        'logistics.Product', on_delete=models.PROTECT, related_name='sales_order_items', verbose_name='Producto'
    )
    description = models.CharField(max_length=500, verbose_name='Descripcion')
    quantity = models.DecimalField(max_digits=12, decimal_places=3, verbose_name='Cantidad')
    delivered_quantity = models.DecimalField(
        max_digits=12, decimal_places=3, default=0, verbose_name='Cantidad Entregada'
    )
    unit = models.ForeignKey('logistics.UnitOfMeasure', on_delete=models.PROTECT, verbose_name='Unidad')
    unit_price = models.DecimalField(max_digits=12, decimal_places=2, verbose_name='Precio Unitario')
    discount = models.DecimalField(max_digits=12, decimal_places=2, default=0, verbose_name='Descuento')
    affectation_type = models.CharField(max_length=2, default='10', verbose_name='Tipo Afectacion')
    igv = models.DecimalField(max_digits=12, decimal_places=2, default=0, verbose_name='IGV')
    subtotal = models.DecimalField(max_digits=12, decimal_places=2, default=0, verbose_name='Subtotal')
    total = models.DecimalField(max_digits=12, decimal_places=2, default=0, verbose_name='Total')

    class Meta:
        verbose_name = 'Item de Pedido'
        verbose_name_plural = 'Items de Pedido'

    def __str__(self):
        return f"{self.description} x {self.quantity}"

    @property
    def pending_quantity(self):
        return self.quantity - self.delivered_quantity

    def calculate_totals(self):
        self.subtotal = (self.quantity * self.unit_price) - self.discount
        if self.affectation_type == '10':
            self.igv = self.subtotal * Decimal('0.18')
        else:
            self.igv = Decimal('0')
        self.total = self.subtotal + self.igv


class PickingOrder(models.Model):
    """Orden de Picking/Preparacion - Warehouse picking order."""

    class Status(models.TextChoices):
        PENDING = 'pending', 'Pendiente'
        IN_PROGRESS = 'in_progress', 'En Proceso'
        COMPLETED = 'completed', 'Completado'
        CANCELLED = 'cancelled', 'Cancelado'

    number = models.CharField(max_length=20, unique=True, verbose_name='Numero')
    sales_order = models.ForeignKey(
        SalesOrder, on_delete=models.CASCADE, related_name='picking_orders', verbose_name='Pedido de Venta'
    )
    warehouse = models.ForeignKey(
        'logistics.Warehouse', on_delete=models.PROTECT, related_name='picking_orders', verbose_name='Almacen'
    )
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.PENDING)
    assigned_to = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='picking_orders', verbose_name='Asignado a'
    )

    scheduled_date = models.DateField(verbose_name='Fecha Programada')
    started_at = models.DateTimeField(null=True, blank=True, verbose_name='Inicio')
    completed_at = models.DateTimeField(null=True, blank=True, verbose_name='Completado')

    notes = models.TextField(blank=True, verbose_name='Notas')
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, related_name='picking_orders_created'
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Orden de Picking'
        verbose_name_plural = 'Ordenes de Picking'
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.number} - {self.sales_order.number}"

    @property
    def progress_percent(self):
        items = self.items.all()
        if not items:
            return 0
        total = items.count()
        picked = items.filter(picked=True).count()
        return int((picked / total) * 100)


class PickingOrderItem(models.Model):
    """Items to pick in a picking order."""
    picking_order = models.ForeignKey(PickingOrder, on_delete=models.CASCADE, related_name='items')
    product = models.ForeignKey(
        'logistics.Product', on_delete=models.PROTECT, related_name='picking_items', verbose_name='Producto'
    )
    quantity_requested = models.DecimalField(max_digits=12, decimal_places=3, verbose_name='Cantidad Solicitada')
    quantity_picked = models.DecimalField(max_digits=12, decimal_places=3, default=0, verbose_name='Cantidad Preparada')
    location = models.CharField(max_length=100, blank=True, verbose_name='Ubicacion en Almacen')
    picked = models.BooleanField(default=False, verbose_name='Preparado')
    picked_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name='items_picked'
    )
    picked_at = models.DateTimeField(null=True, blank=True)
    notes = models.CharField(max_length=300, blank=True, verbose_name='Observacion')

    class Meta:
        verbose_name = 'Item de Picking'
        verbose_name_plural = 'Items de Picking'

    def __str__(self):
        return f"{self.product.name} - {self.quantity_requested}"
