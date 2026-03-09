from django.conf import settings

# Module-level cache to avoid DB queries on every request
_theme_cache = {'data': None, 'company': None, 'ts': 0}


def company_info(request):
    import time
    now = time.time()

    # Refresh cache every 60 seconds
    if _theme_cache['data'] is None or (now - _theme_cache['ts']) > 60:
        theme = {}
        company = None
        try:
            from apps.core.models import Company, SystemConfig
            company = Company.objects.first()
            configs = {
                c.key: c.value
                for c in SystemConfig.objects.filter(
                    key__in=['primary_color', 'accent_color', 'sidebar_color']
                )
            }
            if configs.get('primary_color'):
                theme['primary'] = configs['primary_color']
            if configs.get('accent_color'):
                theme['accent'] = configs['accent_color']
            if configs.get('sidebar_color'):
                theme['sidebar'] = configs['sidebar_color']
        except Exception:
            pass
        _theme_cache['data'] = theme
        _theme_cache['company'] = company
        _theme_cache['ts'] = now

    return {
        'company_config': settings.COMPANY_CONFIG,
        'company': _theme_cache['company'],
        'theme': _theme_cache['data'],
    }
