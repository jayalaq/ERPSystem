from django.conf import settings


def company_info(request):
    from apps.core.models import Company, SystemConfig

    company = None
    theme = {}
    try:
        company = Company.objects.first()
        configs = {c.key: c.value for c in SystemConfig.objects.filter(
            key__in=['primary_color', 'accent_color', 'sidebar_color']
        )}
        if configs.get('primary_color'):
            theme['primary'] = configs['primary_color']
        if configs.get('accent_color'):
            theme['accent'] = configs['accent_color']
        if configs.get('sidebar_color'):
            theme['sidebar'] = configs['sidebar_color']
    except Exception:
        pass

    return {
        'company_config': settings.COMPANY_CONFIG,
        'company': company,
        'theme': theme,
    }
