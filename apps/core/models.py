from django.contrib.auth.models import AbstractUser
from django.db import models
from django.core.validators import RegexValidator
from apps.core.validators import validate_image_file


class User(AbstractUser):
    """Extended user model for ERP system."""

    class Role(models.TextChoices):
        ADMIN = 'admin', 'Administrador'
        MANAGER = 'manager', 'Gerente'
        SALES = 'sales', 'Ventas'
        WAREHOUSE = 'warehouse', 'Almacén'
        ACCOUNTING = 'accounting', 'Contabilidad'
        CASHIER = 'cashier', 'Cajero'

    role = models.CharField(max_length=20, choices=Role.choices, default=Role.SALES)
    phone = models.CharField(max_length=20, blank=True)
    dni = models.CharField(
        max_length=8, blank=True,
        validators=[RegexValidator(r'^\d{8}$', 'DNI debe tener 8 dígitos')]
    )
    avatar = models.ImageField(upload_to='avatars/', blank=True, null=True, validators=[validate_image_file])
    is_active_employee = models.BooleanField(default=True)
    branch = models.ForeignKey(
        'Branch', on_delete=models.SET_NULL, null=True, blank=True, related_name='employees'
    )

    class Meta:
        verbose_name = 'Usuario'
        verbose_name_plural = 'Usuarios'

    def __str__(self):
        return f"{self.get_full_name() or self.username}"


class Company(models.Model):
    """Company/business configuration."""
    name = models.CharField(max_length=200, verbose_name='Razón Social')
    trade_name = models.CharField(max_length=200, blank=True, verbose_name='Nombre Comercial')
    ruc = models.CharField(
        max_length=11, unique=True,
        validators=[RegexValidator(r'^\d{11}$', 'RUC debe tener 11 dígitos')]
    )
    address = models.TextField(verbose_name='Dirección Fiscal')
    ubigeo = models.CharField(max_length=6, blank=True)
    department = models.CharField(max_length=100, blank=True, verbose_name='Departamento')
    province = models.CharField(max_length=100, blank=True, verbose_name='Provincia')
    district = models.CharField(max_length=100, blank=True, verbose_name='Distrito')
    phone = models.CharField(max_length=20, blank=True, verbose_name='Teléfono')
    email = models.EmailField(blank=True)
    website = models.URLField(blank=True)
    logo = models.ImageField(upload_to='company/', blank=True, null=True, validators=[validate_image_file])
    certificate = models.FileField(upload_to='certificates/', blank=True, null=True, verbose_name='Certificado Digital')
    certificate_password = models.CharField(max_length=100, blank=True)
    sol_user = models.CharField(max_length=20, blank=True, verbose_name='Usuario SOL')
    sol_password = models.CharField(max_length=100, blank=True, verbose_name='Clave SOL')
    sunat_production = models.BooleanField(default=False, verbose_name='Producción SUNAT')
    igv_rate = models.DecimalField(max_digits=5, decimal_places=4, default=0.18, verbose_name='Tasa IGV')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Empresa'
        verbose_name_plural = 'Empresas'

    def __str__(self):
        return self.name


class Branch(models.Model):
    """Business branches/locations."""
    company = models.ForeignKey(Company, on_delete=models.CASCADE, related_name='branches')
    name = models.CharField(max_length=200, verbose_name='Nombre de Sucursal')
    code = models.CharField(max_length=10, unique=True, verbose_name='Código')
    address = models.TextField(verbose_name='Dirección')
    phone = models.CharField(max_length=20, blank=True)
    is_main = models.BooleanField(default=False, verbose_name='Sede Principal')
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Sucursal'
        verbose_name_plural = 'Sucursales'

    def __str__(self):
        return f"{self.name} ({self.code})"


class Currency(models.Model):
    """Supported currencies."""
    code = models.CharField(max_length=3, unique=True)
    name = models.CharField(max_length=50)
    symbol = models.CharField(max_length=5)
    exchange_rate = models.DecimalField(max_digits=10, decimal_places=4, default=1)
    is_default = models.BooleanField(default=False)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Moneda'
        verbose_name_plural = 'Monedas'

    def __str__(self):
        return f"{self.code} - {self.name}"


class AuditLog(models.Model):
    """System audit trail."""
    user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    action = models.CharField(max_length=50)
    model_name = models.CharField(max_length=100)
    object_id = models.PositiveIntegerField(null=True)
    description = models.TextField(blank=True)
    ip_address = models.GenericIPAddressField(null=True)
    data = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Log de Auditoría'
        verbose_name_plural = 'Logs de Auditoría'
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.user} - {self.action} - {self.created_at}"


class SystemConfig(models.Model):
    """Key-value system configuration."""
    key = models.CharField(max_length=100, unique=True)
    value = models.TextField()
    description = models.CharField(max_length=255, blank=True)

    class Meta:
        verbose_name = 'Configuración'
        verbose_name_plural = 'Configuraciones'

    def __str__(self):
        return self.key
