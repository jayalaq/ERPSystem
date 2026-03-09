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
    payment_term = models.ForeignKey(
        'PaymentTerm', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='quotations', verbose_name='Termino de Pago'
    )
    delivery_terms = models.CharField(max_length=200, blank=True, verbose_name='Condiciones de Entrega')
    delivery_time = models.CharField(max_length=100, blank=True, verbose_name='Tiempo de Entrega')

    # Price list
    price_list = models.ForeignKey(
        'PriceList', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='quotations', verbose_name='Lista de Precios'
    )

    # Amounts
    subtotal = models.DecimalField(max_digits=12, decimal_places=2, default=0, verbose_name='Subtotal')
    discount_percent = models.DecimalField(max_digits=5, decimal_places=2, default=0, verbose_name='% Descuento')
    discount_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0, verbose_name='Descuento')
    igv = models.DecimalField(max_digits=12, decimal_places=2, default=0, verbose_name='IGV')
    total = models.DecimalField(max_digits=12, decimal_places=2, default=0, verbose_name='Total')

    notes = models.TextField(blank=True, verbose_name='Notas')
    internal_notes = models.TextField(blank=True, verbose_name='Notas Internas')

    # Client signature (base64 PNG data)
    signature = models.TextField(blank=True, verbose_name='Firma del Cliente')
    signed_by = models.CharField(max_length=200, blank=True, verbose_name='Firmado por')
    signed_at = models.DateTimeField(null=True, blank=True, verbose_name='Fecha de Firma')

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
    payment_term = models.ForeignKey(
        'PaymentTerm', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='sales_orders', verbose_name='Termino de Pago'
    )
    price_list = models.ForeignKey(
        'PriceList', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='sales_orders', verbose_name='Lista de Precios'
    )

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


# ============================================
# PRICE LISTS
# ============================================
class PriceList(models.Model):
    """Lista de Precios - configurable por cliente/segmento."""

    class Currency(models.TextChoices):
        PEN = 'PEN', 'Soles (PEN)'
        USD = 'USD', 'Dolares (USD)'

    name = models.CharField(max_length=200, verbose_name='Nombre')
    code = models.CharField(max_length=20, unique=True, verbose_name='Codigo')
    currency = models.CharField(max_length=3, choices=Currency.choices, default=Currency.PEN, verbose_name='Moneda')
    is_active = models.BooleanField(default=True, verbose_name='Activa')
    is_default = models.BooleanField(default=False, verbose_name='Por Defecto')
    valid_from = models.DateField(null=True, blank=True, verbose_name='Vigente Desde')
    valid_until = models.DateField(null=True, blank=True, verbose_name='Vigente Hasta')
    notes = models.TextField(blank=True, verbose_name='Notas')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Lista de Precios'
        verbose_name_plural = 'Listas de Precios'
        ordering = ['name']

    def __str__(self):
        return f"{self.name} ({self.currency})"

    def get_price(self, product):
        """Get the price for a product from this list."""
        item = self.items.filter(product=product).first()
        return item.price if item else product.sale_price


class PriceListItem(models.Model):
    """Precio de un producto en una lista de precios."""
    price_list = models.ForeignKey(PriceList, on_delete=models.CASCADE, related_name='items')
    product = models.ForeignKey(
        'logistics.Product', on_delete=models.CASCADE, related_name='price_list_items', verbose_name='Producto'
    )
    price = models.DecimalField(max_digits=12, decimal_places=2, verbose_name='Precio')
    min_quantity = models.DecimalField(
        max_digits=12, decimal_places=3, default=1, verbose_name='Cantidad Minima'
    )

    class Meta:
        verbose_name = 'Item de Lista de Precios'
        verbose_name_plural = 'Items de Lista de Precios'
        unique_together = ['price_list', 'product', 'min_quantity']
        ordering = ['product__name', 'min_quantity']

    def __str__(self):
        return f"{self.product.name} - {self.price} ({self.price_list.name})"


# ============================================
# PAYMENT TERMS
# ============================================
class PaymentTerm(models.Model):
    """Terminos de Pago - con soporte para cuotas."""
    name = models.CharField(max_length=200, verbose_name='Nombre')
    code = models.CharField(max_length=20, unique=True, verbose_name='Codigo')
    is_active = models.BooleanField(default=True, verbose_name='Activo')
    is_immediate = models.BooleanField(default=False, verbose_name='Pago Inmediato')
    notes = models.TextField(blank=True, verbose_name='Notas')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Termino de Pago'
        verbose_name_plural = 'Terminos de Pago'
        ordering = ['name']

    def __str__(self):
        return self.name

    @property
    def total_days(self):
        """Total days until full payment is due."""
        last = self.installments.order_by('-days').first()
        return last.days if last else 0


class PaymentTermInstallment(models.Model):
    """Cuota de un termino de pago."""
    payment_term = models.ForeignKey(PaymentTerm, on_delete=models.CASCADE, related_name='installments')
    sequence = models.PositiveIntegerField(default=1, verbose_name='Secuencia')
    percentage = models.DecimalField(max_digits=5, decimal_places=2, verbose_name='Porcentaje')
    days = models.PositiveIntegerField(verbose_name='Dias')

    class Meta:
        verbose_name = 'Cuota de Pago'
        verbose_name_plural = 'Cuotas de Pago'
        ordering = ['sequence']
        unique_together = ['payment_term', 'sequence']

    def __str__(self):
        return f"{self.percentage}% a {self.days} dias"


# ============================================
# ACTIVITY LOG (Chatter / Historial)
# ============================================
class SalesActivityLog(models.Model):
    """Historial de actividades - similar al chatter de Odoo."""

    class ActivityType(models.TextChoices):
        STATUS_CHANGE = 'status_change', 'Cambio de Estado'
        NOTE = 'note', 'Nota'
        SIGNATURE = 'signature', 'Firma'
        EMAIL = 'email', 'Email Enviado'
        DOCUMENT = 'document', 'Documento'

    # Polymorphic reference to quotation or order
    quotation = models.ForeignKey(
        SalesQuotation, on_delete=models.CASCADE, null=True, blank=True,
        related_name='activity_logs', verbose_name='Cotizacion'
    )
    order = models.ForeignKey(
        SalesOrder, on_delete=models.CASCADE, null=True, blank=True,
        related_name='activity_logs', verbose_name='Pedido'
    )

    activity_type = models.CharField(
        max_length=20, choices=ActivityType.choices, default=ActivityType.NOTE
    )
    title = models.CharField(max_length=300, verbose_name='Titulo')
    description = models.TextField(blank=True, verbose_name='Descripcion')
    old_value = models.CharField(max_length=50, blank=True, verbose_name='Valor Anterior')
    new_value = models.CharField(max_length=50, blank=True, verbose_name='Valor Nuevo')

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True,
        related_name='sales_activities'
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Actividad'
        verbose_name_plural = 'Actividades'
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.title} - {self.created_at:%d/%m/%Y %H:%M}"
