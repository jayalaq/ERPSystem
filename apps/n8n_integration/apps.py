from django.apps import AppConfig


class N8nIntegrationConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.n8n_integration'
    verbose_name = 'Integración n8n'

    def ready(self):
        import apps.n8n_integration.signals  # noqa: F401
