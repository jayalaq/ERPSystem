from django.db import models
from django.conf import settings
from decimal import Decimal


class BillOfMaterials(models.Model):
    """Lista de Materiales (BOM) - Bill of Materials."""

    class BOMType(models.TextChoices):
        MANUFACTURING = 'manufacturing', 'Fabricacion'
        ASSEMBLY = 'assembly', 'Ensamblaje'
        KIT = 'kit', 'Kit'

    product = models.ForeignKey(
        'logistics.Product', on_delete=models.CASCADE, related_name='boms',
        verbose_name='Producto Final'
    )
    name = models.CharField(max_length=200, verbose_name='Nombre')
    bom_type = models.CharField(max_length=20, choices=BOMType.choices, default=BOMType.MANUFACTURING, verbose_name='Tipo')
    quantity = models.DecimalField(max_digits=12, decimal_places=3, default=1, verbose_name='Cantidad a Producir')
    is_active = models.BooleanField(default=True, verbose_name='Activo')

    # Cost tracking
    estimated_cost = models.DecimalField(max_digits=12, decimal_places=2, default=0, verbose_name='Costo Estimado')
    estimated_time_minutes = models.PositiveIntegerField(default=0, verbose_name='Tiempo Estimado (min)')

    notes = models.TextField(blank=True, verbose_name='Notas')
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, related_name='boms_created'
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Lista de Materiales'
        verbose_name_plural = 'Listas de Materiales'
        ordering = ['product__name']

    def __str__(self):
        return f"BOM: {self.product.name} - {self.name}"

    def calculate_cost(self):
        """Calculate estimated cost from components."""
        total = Decimal('0')
        for comp in self.components.all():
            total += comp.quantity * comp.component.purchase_price
        self.estimated_cost = total
        self.save(update_fields=['estimated_cost'])
        return total

    @property
    def component_count(self):
        return self.components.count()


class BOMComponent(models.Model):
    """Components/materials needed in a BOM."""
    bom = models.ForeignKey(BillOfMaterials, on_delete=models.CASCADE, related_name='components')
    component = models.ForeignKey(
        'logistics.Product', on_delete=models.PROTECT, related_name='used_in_boms',
        verbose_name='Componente'
    )
    quantity = models.DecimalField(max_digits=12, decimal_places=3, verbose_name='Cantidad')
    unit = models.ForeignKey('logistics.UnitOfMeasure', on_delete=models.PROTECT, verbose_name='Unidad')
    notes = models.CharField(max_length=300, blank=True, verbose_name='Notas')

    class Meta:
        verbose_name = 'Componente BOM'
        verbose_name_plural = 'Componentes BOM'

    def __str__(self):
        return f"{self.component.name} x {self.quantity}"

    @property
    def cost(self):
        return self.quantity * self.component.purchase_price


class ProductionOrder(models.Model):
    """Orden de Produccion - Manufacturing/Production Order."""

    class Status(models.TextChoices):
        DRAFT = 'draft', 'Borrador'
        CONFIRMED = 'confirmed', 'Confirmada'
        IN_PRODUCTION = 'in_production', 'En Produccion'
        QUALITY_CHECK = 'quality_check', 'Control de Calidad'
        COMPLETED = 'completed', 'Terminada'
        CANCELLED = 'cancelled', 'Cancelada'

    class Priority(models.TextChoices):
        LOW = 'low', 'Baja'
        NORMAL = 'normal', 'Normal'
        HIGH = 'high', 'Alta'
        URGENT = 'urgent', 'Urgente'

    number = models.CharField(max_length=20, unique=True, verbose_name='Numero')
    bom = models.ForeignKey(
        BillOfMaterials, on_delete=models.PROTECT, related_name='production_orders',
        verbose_name='Lista de Materiales'
    )
    product = models.ForeignKey(
        'logistics.Product', on_delete=models.PROTECT, related_name='production_orders',
        verbose_name='Producto a Fabricar'
    )
    quantity = models.DecimalField(max_digits=12, decimal_places=3, verbose_name='Cantidad a Producir')
    quantity_produced = models.DecimalField(
        max_digits=12, decimal_places=3, default=0, verbose_name='Cantidad Producida'
    )
    quantity_rejected = models.DecimalField(
        max_digits=12, decimal_places=3, default=0, verbose_name='Cantidad Rechazada'
    )

    warehouse = models.ForeignKey(
        'logistics.Warehouse', on_delete=models.PROTECT, related_name='production_orders',
        verbose_name='Almacen'
    )
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.DRAFT)
    priority = models.CharField(max_length=10, choices=Priority.choices, default=Priority.NORMAL, verbose_name='Prioridad')

    planned_date = models.DateField(verbose_name='Fecha Planificada')
    start_date = models.DateTimeField(null=True, blank=True, verbose_name='Fecha de Inicio')
    end_date = models.DateTimeField(null=True, blank=True, verbose_name='Fecha de Fin')

    # Costs
    estimated_cost = models.DecimalField(max_digits=12, decimal_places=2, default=0, verbose_name='Costo Estimado')
    actual_cost = models.DecimalField(max_digits=12, decimal_places=2, default=0, verbose_name='Costo Real')

    # Related to sales order
    sales_order = models.ForeignKey(
        'sales.SalesOrder', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='production_orders', verbose_name='Pedido de Venta'
    )

    notes = models.TextField(blank=True, verbose_name='Notas')
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, related_name='production_orders_created'
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Orden de Produccion'
        verbose_name_plural = 'Ordenes de Produccion'
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.number} - {self.product.name}"

    @property
    def progress_percent(self):
        if self.quantity == 0:
            return 0
        return int((self.quantity_produced / self.quantity) * 100)

    @property
    def pending_quantity(self):
        return self.quantity - self.quantity_produced


class ProductionOrderComponent(models.Model):
    """Components consumed in a production order."""
    production_order = models.ForeignKey(
        ProductionOrder, on_delete=models.CASCADE, related_name='components'
    )
    component = models.ForeignKey(
        'logistics.Product', on_delete=models.PROTECT, related_name='production_consumptions',
        verbose_name='Componente'
    )
    quantity_required = models.DecimalField(max_digits=12, decimal_places=3, verbose_name='Cantidad Requerida')
    quantity_consumed = models.DecimalField(
        max_digits=12, decimal_places=3, default=0, verbose_name='Cantidad Consumida'
    )
    unit = models.ForeignKey('logistics.UnitOfMeasure', on_delete=models.PROTECT, verbose_name='Unidad')
    is_available = models.BooleanField(default=False, verbose_name='Disponible')

    class Meta:
        verbose_name = 'Componente de Produccion'
        verbose_name_plural = 'Componentes de Produccion'

    def __str__(self):
        return f"{self.component.name} x {self.quantity_required}"

    @property
    def pending_quantity(self):
        return self.quantity_required - self.quantity_consumed
