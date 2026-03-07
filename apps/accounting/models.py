from django.db import models
from django.conf import settings
import uuid


class Invoice(models.Model):
    """Electronic invoice (Comprobante Electrónico)."""

    class DocType(models.TextChoices):
        FACTURA = '01', 'Factura'
        BOLETA = '03', 'Boleta de Venta'
        NOTA_CREDITO = '07', 'Nota de Crédito'
        NOTA_DEBITO = '08', 'Nota de Débito'

    class Status(models.TextChoices):
        DRAFT = 'draft', 'Borrador'
        ISSUED = 'issued', 'Emitida'
        SENT = 'sent', 'Enviada a SUNAT'
        ACCEPTED = 'accepted', 'Aceptada por SUNAT'
        REJECTED = 'rejected', 'Rechazada por SUNAT'
        CANCELLED = 'cancelled', 'Anulada'
        VOIDED = 'voided', 'Comunicación de Baja'

    class PaymentCondition(models.TextChoices):
        CASH = 'cash', 'Contado'
        CREDIT = 'credit', 'Crédito'

    uuid = models.UUIDField(default=uuid.uuid4, editable=False, unique=True)
    doc_type = models.CharField(max_length=2, choices=DocType.choices, verbose_name='Tipo Comprobante')
    series = models.CharField(max_length=4, verbose_name='Serie')
    correlative = models.PositiveIntegerField(verbose_name='Correlativo')
    issue_date = models.DateField(verbose_name='Fecha de Emisión')
    due_date = models.DateField(null=True, blank=True, verbose_name='Fecha de Vencimiento')
    customer = models.ForeignKey('crm.Customer', on_delete=models.PROTECT, related_name='invoices')
    currency = models.ForeignKey('core.Currency', on_delete=models.PROTECT, null=True, blank=True)
    exchange_rate = models.DecimalField(max_digits=10, decimal_places=4, default=1, verbose_name='Tipo de Cambio')
    payment_condition = models.CharField(
        max_length=10, choices=PaymentCondition.choices, default=PaymentCondition.CASH,
        verbose_name='Condición de Pago'
    )
    # Related document (for credit/debit notes)
    related_doc_type = models.CharField(max_length=2, blank=True)
    related_series = models.CharField(max_length=4, blank=True)
    related_correlative = models.PositiveIntegerField(null=True, blank=True)
    related_reason = models.TextField(blank=True, verbose_name='Motivo')

    # Amounts
    op_gravada = models.DecimalField(max_digits=12, decimal_places=2, default=0, verbose_name='Op. Gravada')
    op_exonerada = models.DecimalField(max_digits=12, decimal_places=2, default=0, verbose_name='Op. Exonerada')
    op_inafecta = models.DecimalField(max_digits=12, decimal_places=2, default=0, verbose_name='Op. Inafecta')
    op_gratuita = models.DecimalField(max_digits=12, decimal_places=2, default=0, verbose_name='Op. Gratuita')
    discount_total = models.DecimalField(max_digits=12, decimal_places=2, default=0, verbose_name='Descuento Total')
    igv = models.DecimalField(max_digits=12, decimal_places=2, default=0, verbose_name='IGV')
    total = models.DecimalField(max_digits=12, decimal_places=2, default=0, verbose_name='Total')
    amount_in_words = models.CharField(max_length=500, blank=True, verbose_name='Monto en Letras')

    # Status & SUNAT
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.DRAFT)
    sunat_response_code = models.CharField(max_length=10, blank=True)
    sunat_response_description = models.TextField(blank=True)
    sunat_ticket = models.CharField(max_length=100, blank=True)
    hash_code = models.CharField(max_length=100, blank=True)
    qr_code = models.TextField(blank=True)
    xml_file = models.FileField(upload_to='invoices/xml/', blank=True, null=True)
    pdf_file = models.FileField(upload_to='invoices/pdf/', blank=True, null=True)
    cdr_file = models.FileField(upload_to='invoices/cdr/', blank=True, null=True)

    # Metadata
    pos_sale = models.OneToOneField(
        'pos.POSSale', on_delete=models.SET_NULL, null=True, blank=True, related_name='invoice'
    )
    notes = models.TextField(blank=True, verbose_name='Observaciones')
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, related_name='invoices'
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Comprobante'
        verbose_name_plural = 'Comprobantes'
        ordering = ['-created_at']
        unique_together = ['doc_type', 'series', 'correlative']

    def __str__(self):
        return f"{self.get_doc_type_display()} {self.series}-{self.correlative:08d}"

    @property
    def full_number(self):
        return f"{self.series}-{self.correlative:08d}"


class InvoiceItem(models.Model):
    """Invoice line items."""
    invoice = models.ForeignKey(Invoice, on_delete=models.CASCADE, related_name='items')
    product = models.ForeignKey('logistics.Product', on_delete=models.PROTECT, related_name='invoice_items')
    description = models.CharField(max_length=500, verbose_name='Descripción')
    unit = models.ForeignKey('logistics.UnitOfMeasure', on_delete=models.PROTECT)
    quantity = models.DecimalField(max_digits=12, decimal_places=3, verbose_name='Cantidad')
    unit_price = models.DecimalField(max_digits=12, decimal_places=2, verbose_name='Precio Unitario')
    discount = models.DecimalField(max_digits=12, decimal_places=2, default=0, verbose_name='Descuento')
    affectation_type = models.CharField(max_length=2, default='10', verbose_name='Tipo Afectación')
    igv = models.DecimalField(max_digits=12, decimal_places=2, default=0, verbose_name='IGV')
    subtotal = models.DecimalField(max_digits=12, decimal_places=2, verbose_name='Subtotal')
    total = models.DecimalField(max_digits=12, decimal_places=2, verbose_name='Total')

    class Meta:
        verbose_name = 'Ítem de Comprobante'
        verbose_name_plural = 'Ítems de Comprobante'

    def __str__(self):
        return f"{self.description} x {self.quantity}"


class PaymentRecord(models.Model):
    """Payment records for invoices (accounts receivable)."""

    class PaymentMethod(models.TextChoices):
        CASH = 'cash', 'Efectivo'
        BANK_TRANSFER = 'transfer', 'Transferencia Bancaria'
        CARD = 'card', 'Tarjeta'
        CHECK = 'check', 'Cheque'
        YAPE = 'yape', 'Yape'
        PLIN = 'plin', 'Plin'

    invoice = models.ForeignKey(Invoice, on_delete=models.CASCADE, related_name='payments')
    payment_date = models.DateField(verbose_name='Fecha de Pago')
    amount = models.DecimalField(max_digits=12, decimal_places=2, verbose_name='Monto')
    payment_method = models.CharField(max_length=20, choices=PaymentMethod.choices)
    reference = models.CharField(max_length=100, blank=True, verbose_name='Referencia')
    notes = models.TextField(blank=True)
    recorded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, related_name='payment_records'
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Registro de Pago'
        verbose_name_plural = 'Registros de Pago'
        ordering = ['-payment_date']

    def __str__(self):
        return f"Pago {self.amount} - {self.invoice}"


class AccountPayable(models.Model):
    """Accounts payable (supplier invoices)."""

    class Status(models.TextChoices):
        PENDING = 'pending', 'Pendiente'
        PARTIAL = 'partial', 'Parcialmente Pagado'
        PAID = 'paid', 'Pagado'
        OVERDUE = 'overdue', 'Vencido'

    supplier = models.ForeignKey('crm.Supplier', on_delete=models.CASCADE, related_name='payables')
    invoice_number = models.CharField(max_length=50, verbose_name='Nro. Factura Proveedor')
    invoice_date = models.DateField(verbose_name='Fecha de Factura')
    due_date = models.DateField(verbose_name='Fecha de Vencimiento')
    total = models.DecimalField(max_digits=12, decimal_places=2, verbose_name='Total')
    paid_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0, verbose_name='Monto Pagado')
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.PENDING)
    purchase_order = models.ForeignKey(
        'logistics.PurchaseOrder', on_delete=models.SET_NULL, null=True, blank=True, related_name='payables'
    )
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Cuenta por Pagar'
        verbose_name_plural = 'Cuentas por Pagar'
        ordering = ['due_date']

    def __str__(self):
        return f"{self.supplier.name} - {self.invoice_number}"

    @property
    def balance(self):
        return self.total - self.paid_amount


class DocumentSeries(models.Model):
    """Document series configuration."""
    doc_type = models.CharField(max_length=2, choices=Invoice.DocType.choices, verbose_name='Tipo')
    series = models.CharField(max_length=4, verbose_name='Serie')
    next_correlative = models.PositiveIntegerField(default=1, verbose_name='Siguiente Correlativo')
    branch = models.ForeignKey('core.Branch', on_delete=models.CASCADE, related_name='document_series')
    is_active = models.BooleanField(default=True)

    class Meta:
        verbose_name = 'Serie de Documento'
        verbose_name_plural = 'Series de Documentos'
        unique_together = ['doc_type', 'series']

    def __str__(self):
        return f"{self.get_doc_type_display()} - {self.series}"

    def get_next_number(self):
        current = self.next_correlative
        self.next_correlative += 1
        self.save(update_fields=['next_correlative'])
        return current
