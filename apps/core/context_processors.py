from django.conf import settings


def company_info(request):
    return {
        'company_config': settings.COMPANY_CONFIG,
    }
