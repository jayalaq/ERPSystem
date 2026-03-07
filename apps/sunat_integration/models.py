from django.db import models


class SunatLog(models.Model):
    """Log of SUNAT API interactions."""

    class Action(models.TextChoices):
        SEND_INVOICE = 'send_invoice', 'Enviar Comprobante'
        CONSULT_STATUS = 'consult_status', 'Consultar Estado'
        VOID = 'void', 'Comunicación de Baja'
        CONSULT_RUC = 'consult_ruc', 'Consultar RUC'
        EXCHANGE_RATE = 'exchange_rate', 'Tipo de Cambio'

    action = models.CharField(max_length=30, choices=Action.choices)
    document_type = models.CharField(max_length=20, blank=True)
    document_number = models.CharField(max_length=50, blank=True)
    request_data = models.JSONField(default=dict, blank=True)
    response_data = models.JSONField(default=dict, blank=True)
    response_code = models.CharField(max_length=10, blank=True)
    success = models.BooleanField(default=False)
    error_message = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Log SUNAT'
        verbose_name_plural = 'Logs SUNAT'
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.get_action_display()} - {self.document_number} - {'OK' if self.success else 'ERROR'}"
