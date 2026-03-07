from django.db import models
from django.conf import settings


class Category(models.Model):
    """Product categories."""
    name = models.CharField(max_length=200, verbose_name='Nombre')
    slug = models.SlugField(unique=True)
    parent = models.ForeignKey('self', on_delete=models.CASCADE, null=True, blank=True, related_name='children')
    description = models.TextField(blank=True)
    image = models.ImageField(upload_to='categories/', blank=True, null=True)
    is_active = models.BooleanField(default=True)
    order = models.PositiveIntegerField(default=0)

    class Meta:
        verbose_name = 'Categoría'
        verbose_name_plural = 'Categorías'
        ordering = ['order', 'name']

    def __str__(self):
        return self.name


class Brand(models.Model):
    """Product brands."""
    name = models.CharField(max_length=200, verbose_name='Nombre')
    slug = models.SlugField(unique=True)
    logo = models.ImageField(upload_to='brands/', blank=True, null=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        verbose_name = 'Marca'
        verbose_name_plural = 'Marcas'
        ordering = ['name']

    def __str__(self):
        return self.name


class UnitOfMeasure(models.Model):
    """Units of measure (SUNAT catalog)."""
    code = models.CharField(max_length=10, unique=True, verbose_name='Código SUNAT')
    name = models.CharField(max_length=100, verbose_name='Nombre')
    abbreviation = models.CharField(max_length=10, verbose_name='Abreviatura')

    class Meta:
        verbose_name = 'Unidad de Medida'
        verbose_name_plural = 'Unidades de Medida'

    def __str__(self):
        return f"{self.abbreviation} - {self.name}"


class Product(models.Model):
    """Product/Service model."""

    class ProductType(models.TextChoices):
        PRODUCT = 'product', 'Producto'
        SERVICE = 'service', 'Servicio'

    class AffectationType(models.TextChoices):
        GRAVADO = '10', 'Gravado - Operación Onerosa'
        EXONERADO = '20', 'Exonerado - Operación Onerosa'
        INAFECTO = '30', 'Inafecto - Operación Onerosa'
        GRATUITO = '21', 'Exonerado - Transferencia Gratuita'

    product_type = models.CharField(max_length=10, choices=ProductType.choices, default=ProductType.PRODUCT)
    sku = models.CharField(max_length=50, unique=True, verbose_name='SKU/Código')
    barcode = models.CharField(max_length=50, blank=True, verbose_name='Código de Barras')
    name = models.CharField(max_length=300, verbose_name='Nombre')
    description = models.TextField(blank=True, verbose_name='Descripción')
    category = models.ForeignKey(Category, on_delete=models.SET_NULL, null=True, blank=True, related_name='products')
    brand = models.ForeignKey(Brand, on_delete=models.SET_NULL, null=True, blank=True, related_name='products')
    unit = models.ForeignKey(UnitOfMeasure, on_delete=models.PROTECT, related_name='products')
    affectation_type = models.CharField(
        max_length=2, choices=AffectationType.choices, default=AffectationType.GRAVADO,
        verbose_name='Tipo de Afectación IGV'
    )
    purchase_price = models.DecimalField(max_digits=12, decimal_places=2, default=0, verbose_name='Precio de Compra')
    sale_price = models.DecimalField(max_digits=12, decimal_places=2, default=0, verbose_name='Precio de Venta')
    wholesale_price = models.DecimalField(max_digits=12, decimal_places=2, default=0, verbose_name='Precio Mayorista')
    minimum_price = models.DecimalField(max_digits=12, decimal_places=2, default=0, verbose_name='Precio Mínimo')
    min_stock = models.DecimalField(max_digits=12, decimal_places=3, default=0, verbose_name='Stock Mínimo')
    max_stock = models.DecimalField(max_digits=12, decimal_places=3, default=0, verbose_name='Stock Máximo')
    image = models.ImageField(upload_to='products/', blank=True, null=True)
    is_active = models.BooleanField(default=True)
    track_inventory = models.BooleanField(default=True, verbose_name='Control de Inventario')
    allow_negative_stock = models.BooleanField(default=False, verbose_name='Permitir Stock Negativo')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Producto'
        verbose_name_plural = 'Productos'
        ordering = ['name']

    def __str__(self):
        return f"{self.sku} - {self.name}"

    @property
    def total_stock(self):
        return sum(s.quantity for s in self.stock_levels.all())


class Warehouse(models.Model):
    """Warehouse/storage locations."""
    name = models.CharField(max_length=200, verbose_name='Nombre')
    code = models.CharField(max_length=20, unique=True, verbose_name='Código')
    address = models.TextField(blank=True, verbose_name='Dirección')
    branch = models.ForeignKey('core.Branch', on_delete=models.CASCADE, related_name='warehouses')
    manager = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name='managed_warehouses'
    )
    is_active = models.BooleanField(default=True)
    is_default = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Almacén'
        verbose_name_plural = 'Almacenes'

    def __str__(self):
        return f"{self.name} ({self.code})"


class StockLevel(models.Model):
    """Current stock level per product per warehouse."""
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='stock_levels')
    warehouse = models.ForeignKey(Warehouse, on_delete=models.CASCADE, related_name='stock_levels')
    quantity = models.DecimalField(max_digits=12, decimal_places=3, default=0, verbose_name='Cantidad')
    reserved = models.DecimalField(max_digits=12, decimal_places=3, default=0, verbose_name='Reservado')
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Nivel de Stock'
        verbose_name_plural = 'Niveles de Stock'
        unique_together = ['product', 'warehouse']

    def __str__(self):
        return f"{self.product.name} @ {self.warehouse.name}: {self.quantity}"

    @property
    def available(self):
        return self.quantity - self.reserved


class StockMovement(models.Model):
    """Inventory movements (in/out/transfer)."""

    class MovementType(models.TextChoices):
        IN = 'in', 'Entrada'
        OUT = 'out', 'Salida'
        TRANSFER = 'transfer', 'Transferencia'
        ADJUSTMENT = 'adjustment', 'Ajuste'
        RETURN = 'return', 'Devolución'

    movement_type = models.CharField(max_length=20, choices=MovementType.choices)
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='movements')
    warehouse = models.ForeignKey(Warehouse, on_delete=models.CASCADE, related_name='movements')
    destination_warehouse = models.ForeignKey(
        Warehouse, on_delete=models.CASCADE, null=True, blank=True, related_name='incoming_movements'
    )
    quantity = models.DecimalField(max_digits=12, decimal_places=3, verbose_name='Cantidad')
    unit_cost = models.DecimalField(max_digits=12, decimal_places=2, default=0, verbose_name='Costo Unitario')
    reference = models.CharField(max_length=100, blank=True, verbose_name='Referencia')
    reference_type = models.CharField(max_length=50, blank=True)
    reference_id = models.PositiveIntegerField(null=True, blank=True)
    reason = models.TextField(blank=True, verbose_name='Motivo')
    performed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, related_name='stock_movements'
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Movimiento de Stock'
        verbose_name_plural = 'Movimientos de Stock'
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.get_movement_type_display()} - {self.product.name} x {self.quantity}"


class PurchaseOrder(models.Model):
    """Purchase orders to suppliers."""

    class Status(models.TextChoices):
        DRAFT = 'draft', 'Borrador'
        CONFIRMED = 'confirmed', 'Confirmada'
        PARTIAL = 'partial', 'Parcialmente Recibida'
        RECEIVED = 'received', 'Recibida'
        CANCELLED = 'cancelled', 'Cancelada'

    number = models.CharField(max_length=20, unique=True, verbose_name='Número')
    supplier = models.ForeignKey('crm.Supplier', on_delete=models.CASCADE, related_name='purchase_orders')
    warehouse = models.ForeignKey(Warehouse, on_delete=models.CASCADE, related_name='purchase_orders')
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.DRAFT)
    order_date = models.DateField(verbose_name='Fecha de Orden')
    expected_date = models.DateField(null=True, blank=True, verbose_name='Fecha Esperada')
    subtotal = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    igv = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    total = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    notes = models.TextField(blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, related_name='purchase_orders'
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Orden de Compra'
        verbose_name_plural = 'Órdenes de Compra'
        ordering = ['-created_at']

    def __str__(self):
        return self.number


class PurchaseOrderItem(models.Model):
    """Items in a purchase order."""
    order = models.ForeignKey(PurchaseOrder, on_delete=models.CASCADE, related_name='items')
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='purchase_items')
    quantity = models.DecimalField(max_digits=12, decimal_places=3, verbose_name='Cantidad')
    received_quantity = models.DecimalField(max_digits=12, decimal_places=3, default=0, verbose_name='Recibido')
    unit_price = models.DecimalField(max_digits=12, decimal_places=2, verbose_name='Precio Unitario')
    subtotal = models.DecimalField(max_digits=12, decimal_places=2)

    class Meta:
        verbose_name = 'Ítem de Orden de Compra'
        verbose_name_plural = 'Ítems de Orden de Compra'

    def __str__(self):
        return f"{self.product.name} x {self.quantity}"
