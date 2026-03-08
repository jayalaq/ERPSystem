from django.db import models


class ContactMessage(models.Model):
    """Messages from the public contact form."""

    class Status(models.TextChoices):
        NEW = 'new', 'Nuevo'
        READ = 'read', 'Leído'
        CONVERTED = 'converted', 'Convertido a Oportunidad'
        ARCHIVED = 'archived', 'Archivado'

    class ServiceInterest(models.TextChoices):
        FACTURACION = 'facturacion', 'Facturación Electrónica'
        RPA = 'rpa', 'Automatización de Procesos (RPA)'
        MARKETING = 'marketing', 'Marketing Pos-venta'
        WEB = 'web', 'Desarrollo Web'
        CONSULTORIA = 'consultoria', 'Consultoría Informática'
        ERP = 'erp', 'Sistema ERP / POS'
        OTHER = 'other', 'Otro'

    name = models.CharField(max_length=200, verbose_name='Nombre')
    email = models.EmailField(verbose_name='Correo Electrónico')
    phone = models.CharField(max_length=20, blank=True, verbose_name='Teléfono')
    company = models.CharField(max_length=200, blank=True, verbose_name='Empresa')
    ruc = models.CharField(max_length=11, blank=True, verbose_name='RUC')
    service_interest = models.CharField(
        max_length=20, choices=ServiceInterest.choices,
        default=ServiceInterest.CONSULTORIA, verbose_name='Servicio de Interés'
    )
    message = models.TextField(verbose_name='Mensaje')
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.NEW)
    opportunity = models.ForeignKey(
        'crm.Opportunity', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='contact_messages', verbose_name='Oportunidad Asociada'
    )
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Mensaje de Contacto'
        verbose_name_plural = 'Mensajes de Contacto'
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.name} - {self.get_service_interest_display()} ({self.created_at:%d/%m/%Y})"
