from django.db import models
from django.core.validators import RegexValidator


class Customer(models.Model):
    """Customer/Client model for CRM."""

    class DocType(models.TextChoices):
        DNI = 'DNI', 'DNI'
        RUC = 'RUC', 'RUC'
        CE = 'CE', 'Carné de Extranjería'
        PASSPORT = 'PAS', 'Pasaporte'

    class CustomerType(models.TextChoices):
        INDIVIDUAL = 'individual', 'Persona Natural'
        BUSINESS = 'business', 'Persona Jurídica'

    customer_type = models.CharField(max_length=20, choices=CustomerType.choices, default=CustomerType.INDIVIDUAL)
    doc_type = models.CharField(max_length=3, choices=DocType.choices, default=DocType.DNI, verbose_name='Tipo Doc.')
    doc_number = models.CharField(max_length=20, unique=True, verbose_name='Nro. Documento')
    name = models.CharField(max_length=300, verbose_name='Nombre / Razón Social')
    trade_name = models.CharField(max_length=300, blank=True, verbose_name='Nombre Comercial')
    email = models.EmailField(blank=True)
    phone = models.CharField(max_length=20, blank=True, verbose_name='Teléfono')
    mobile = models.CharField(max_length=20, blank=True, verbose_name='Celular')
    address = models.TextField(blank=True, verbose_name='Dirección')
    ubigeo = models.CharField(max_length=6, blank=True)
    department = models.CharField(max_length=100, blank=True, verbose_name='Departamento')
    province = models.CharField(max_length=100, blank=True, verbose_name='Provincia')
    district = models.CharField(max_length=100, blank=True, verbose_name='Distrito')
    credit_limit = models.DecimalField(max_digits=12, decimal_places=2, default=0, verbose_name='Límite de Crédito')
    credit_days = models.PositiveIntegerField(default=0, verbose_name='Días de Crédito')
    tags = models.CharField(max_length=500, blank=True, verbose_name='Etiquetas')
    notes = models.TextField(blank=True, verbose_name='Notas')
    is_active = models.BooleanField(default=True)
    assigned_to = models.ForeignKey(
        'core.User', on_delete=models.SET_NULL, null=True, blank=True, related_name='assigned_customers'
    )
    created_by = models.ForeignKey(
        'core.User', on_delete=models.SET_NULL, null=True, related_name='created_customers'
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Cliente'
        verbose_name_plural = 'Clientes'
        ordering = ['name']

    def __str__(self):
        return f"{self.doc_number} - {self.name}"


class CustomerContact(models.Model):
    """Contact persons for a customer."""
    customer = models.ForeignKey(Customer, on_delete=models.CASCADE, related_name='contacts')
    name = models.CharField(max_length=200, verbose_name='Nombre')
    position = models.CharField(max_length=100, blank=True, verbose_name='Cargo')
    email = models.EmailField(blank=True)
    phone = models.CharField(max_length=20, blank=True)
    is_primary = models.BooleanField(default=False, verbose_name='Contacto Principal')

    class Meta:
        verbose_name = 'Contacto'
        verbose_name_plural = 'Contactos'

    def __str__(self):
        return f"{self.name} - {self.customer.name}"


class Supplier(models.Model):
    """Supplier/Vendor model."""

    class DocType(models.TextChoices):
        RUC = 'RUC', 'RUC'
        DNI = 'DNI', 'DNI'

    doc_type = models.CharField(max_length=3, choices=DocType.choices, default=DocType.RUC)
    doc_number = models.CharField(max_length=20, unique=True, verbose_name='Nro. Documento')
    name = models.CharField(max_length=300, verbose_name='Razón Social')
    trade_name = models.CharField(max_length=300, blank=True)
    email = models.EmailField(blank=True)
    phone = models.CharField(max_length=20, blank=True)
    address = models.TextField(blank=True, verbose_name='Dirección')
    contact_name = models.CharField(max_length=200, blank=True, verbose_name='Contacto')
    payment_terms = models.PositiveIntegerField(default=30, verbose_name='Plazo de Pago (días)')
    bank_name = models.CharField(max_length=100, blank=True, verbose_name='Banco')
    bank_account = models.CharField(max_length=50, blank=True, verbose_name='Nro. Cuenta')
    bank_cci = models.CharField(max_length=50, blank=True, verbose_name='CCI')
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Proveedor'
        verbose_name_plural = 'Proveedores'
        ordering = ['name']

    def __str__(self):
        return f"{self.doc_number} - {self.name}"


class Opportunity(models.Model):
    """Sales opportunities for CRM pipeline."""

    class Stage(models.TextChoices):
        PROSPECTING = 'prospecting', 'Prospección'
        QUALIFICATION = 'qualification', 'Calificación'
        PROPOSAL = 'proposal', 'Propuesta'
        NEGOTIATION = 'negotiation', 'Negociación'
        CLOSED_WON = 'closed_won', 'Ganada'
        CLOSED_LOST = 'closed_lost', 'Perdida'

    class Priority(models.TextChoices):
        LOW = 'low', 'Baja'
        MEDIUM = 'medium', 'Media'
        HIGH = 'high', 'Alta'
        URGENT = 'urgent', 'Urgente'

    customer = models.ForeignKey(Customer, on_delete=models.CASCADE, related_name='opportunities')
    title = models.CharField(max_length=300, verbose_name='Título')
    description = models.TextField(blank=True, verbose_name='Descripción')
    stage = models.CharField(max_length=20, choices=Stage.choices, default=Stage.PROSPECTING)
    priority = models.CharField(max_length=10, choices=Priority.choices, default=Priority.MEDIUM)
    expected_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0, verbose_name='Monto Esperado')
    probability = models.PositiveIntegerField(default=50, verbose_name='Probabilidad (%)')
    expected_close_date = models.DateField(null=True, blank=True, verbose_name='Fecha Esperada de Cierre')
    assigned_to = models.ForeignKey(
        'core.User', on_delete=models.SET_NULL, null=True, blank=True, related_name='opportunities'
    )
    source = models.CharField(max_length=100, blank=True, verbose_name='Fuente')
    lost_reason = models.TextField(blank=True, verbose_name='Motivo de Pérdida')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Oportunidad'
        verbose_name_plural = 'Oportunidades'
        ordering = ['-created_at']

    def __str__(self):
        return self.title

    @property
    def weighted_amount(self):
        return self.expected_amount * self.probability / 100


class Interaction(models.Model):
    """Customer interaction tracking."""

    class InteractionType(models.TextChoices):
        CALL = 'call', 'Llamada'
        EMAIL = 'email', 'Correo'
        MEETING = 'meeting', 'Reunión'
        VISIT = 'visit', 'Visita'
        WHATSAPP = 'whatsapp', 'WhatsApp'
        OTHER = 'other', 'Otro'

    customer = models.ForeignKey(Customer, on_delete=models.CASCADE, related_name='interactions')
    opportunity = models.ForeignKey(
        Opportunity, on_delete=models.SET_NULL, null=True, blank=True, related_name='interactions'
    )
    interaction_type = models.CharField(max_length=20, choices=InteractionType.choices)
    subject = models.CharField(max_length=300, verbose_name='Asunto')
    description = models.TextField(blank=True, verbose_name='Descripción')
    date = models.DateTimeField(verbose_name='Fecha')
    next_action = models.TextField(blank=True, verbose_name='Próxima Acción')
    next_action_date = models.DateField(null=True, blank=True)
    performed_by = models.ForeignKey(
        'core.User', on_delete=models.SET_NULL, null=True, related_name='interactions'
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Interacción'
        verbose_name_plural = 'Interacciones'
        ordering = ['-date']

    def __str__(self):
        return f"{self.subject} - {self.customer.name}"
