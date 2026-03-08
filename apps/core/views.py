import os

from django.contrib.auth import login, logout
from django.contrib.auth.decorators import login_required
from django.shortcuts import render, redirect
from django.db.models import Sum, Count, Q, F
from django.utils import timezone
from datetime import timedelta
from decimal import Decimal

IS_TESTING = os.environ.get('ENVIRONMENT') == 'testing'

from .forms import LoginForm
from apps.accounting.models import Invoice
from apps.crm.models import Customer, Opportunity
from apps.pos.models import POSSale
from apps.logistics.models import Product, StockLevel


def landing_page(request):
    if request.user.is_authenticated:
        return redirect('dashboard')
    return render(request, 'core/landing.html')


def google_login_redirect(request):
    """Redirect to allauth Google login flow."""
    return redirect('/accounts/google/login/')


def login_view(request):
    if request.user.is_authenticated:
        return redirect('dashboard')
    if request.method == 'POST':
        form = LoginForm(request, data=request.POST)
        if form.is_valid():
            login(request, form.get_user())
            return redirect('dashboard')
    else:
        form = LoginForm()
    return render(request, 'core/login.html', {'form': form, 'is_testing': IS_TESTING})


def logout_view(request):
    logout(request)
    return redirect('website:landing')


@login_required
def dashboard(request):
    today = timezone.now().date()
    month_start = today.replace(day=1)
    last_30_days = today - timedelta(days=30)

    # Sales stats
    monthly_sales = POSSale.objects.filter(
        created_at__date__gte=month_start, status='completed'
    ).aggregate(total=Sum('total'), count=Count('id'))

    today_sales = POSSale.objects.filter(
        created_at__date=today, status='completed'
    ).aggregate(total=Sum('total'), count=Count('id'))

    # Invoice stats
    pending_invoices = Invoice.objects.filter(status='draft').count()
    accepted_invoices = Invoice.objects.filter(
        status='accepted', created_at__date__gte=month_start
    ).count()

    # CRM stats
    total_customers = Customer.objects.filter(is_active=True).count()
    active_opportunities = Opportunity.objects.exclude(
        stage__in=['closed_won', 'closed_lost']
    ).count()
    pipeline_value = Opportunity.objects.exclude(
        stage__in=['closed_won', 'closed_lost']
    ).aggregate(total=Sum('expected_amount'))['total'] or Decimal('0')

    # Low stock alerts
    low_stock_products = Product.objects.filter(
        track_inventory=True, is_active=True
    ).annotate(
        current_stock=Sum('stock_levels__quantity')
    ).filter(current_stock__lte=F('min_stock')).count()

    # Recent sales
    recent_sales = POSSale.objects.filter(status='completed').select_related('customer', 'seller')[:10]

    # Top products (last 30 days)
    from apps.pos.models import POSSaleItem
    top_products = POSSaleItem.objects.filter(
        sale__created_at__date__gte=last_30_days,
        sale__status='completed'
    ).values('product__name').annotate(
        total_qty=Sum('quantity'),
        total_amount=Sum('total')
    ).order_by('-total_amount')[:5]

    context = {
        'monthly_sales_total': monthly_sales['total'] or Decimal('0'),
        'monthly_sales_count': monthly_sales['count'] or 0,
        'today_sales_total': today_sales['total'] or Decimal('0'),
        'today_sales_count': today_sales['count'] or 0,
        'pending_invoices': pending_invoices,
        'accepted_invoices': accepted_invoices,
        'total_customers': total_customers,
        'active_opportunities': active_opportunities,
        'pipeline_value': pipeline_value,
        'low_stock_products': low_stock_products,
        'recent_sales': recent_sales,
        'top_products': top_products,
    }
    return render(request, 'dashboard/dashboard.html', context)


def health_check(request):
    """Health check endpoint for load balancers and monitoring."""
    import os
    from django.http import JsonResponse
    from django.db import connection

    status = {'status': 'healthy', 'environment': os.environ.get('ENVIRONMENT', 'development')}
    try:
        with connection.cursor() as cursor:
            cursor.execute('SELECT 1')
        status['database'] = 'connected'
    except Exception as e:
        status['database'] = f'error: {e}'
        status['status'] = 'unhealthy'

    code = 200 if status['status'] == 'healthy' else 503
    return JsonResponse(status, status=code)


@login_required
def video_tutorials(request):
    """Video tutorials page."""
    tutorials = [
        {'title': 'Como usar el Punto de Venta', 'description': 'Aprende a usar el terminal POS, abrir/cerrar sesiones y procesar ventas.', 'category': 'POS', 'icon': 'bi-cart3'},
        {'title': 'Gestion de Clientes', 'description': 'Crear, editar y gestionar clientes en el CRM.', 'category': 'CRM', 'icon': 'bi-people'},
        {'title': 'Emision de Comprobantes', 'description': 'Como emitir facturas, boletas y notas de credito electronicas.', 'category': 'Facturacion', 'icon': 'bi-file-earmark-text'},
        {'title': 'Control de Inventario', 'description': 'Gestionar productos, stock y movimientos de inventario.', 'category': 'Logistica', 'icon': 'bi-box-seam'},
        {'title': 'Envio a SUNAT', 'description': 'Proceso de envio de comprobantes electronicos a SUNAT.', 'category': 'SUNAT', 'icon': 'bi-cloud-upload'},
        {'title': 'Guias de Remision', 'description': 'Crear y gestionar guias de remision para traslado de mercaderia.', 'category': 'Logistica', 'icon': 'bi-send'},
        {'title': 'Caja Chica', 'description': 'Administrar caja chica y registrar gastos menores.', 'category': 'Finanzas', 'icon': 'bi-cash-stack'},
        {'title': 'Reportes Financieros', 'description': 'Generar reportes de ventas, compras y contabilidad.', 'category': 'Reportes', 'icon': 'bi-graph-up'},
    ]
    return render(request, 'core/video_tutorials.html', {'tutorials': tutorials})


@login_required
def system_customize(request):
    """System customization - company branding and settings."""
    from apps.core.models import Company, SystemConfig

    company = Company.objects.first()

    if request.method == 'POST':
        if company is None:
            company = Company()
        company.name = request.POST.get('name', company.name if company else '')
        company.trade_name = request.POST.get('trade_name', '')
        company.ruc = request.POST.get('ruc', company.ruc if company else '')
        company.address = request.POST.get('address', '')
        company.phone = request.POST.get('phone', '')
        company.email = request.POST.get('email', '')
        company.website = request.POST.get('website', '')

        if 'logo' in request.FILES:
            company.logo = request.FILES['logo']

        company.save()

        # Save system configs
        for key in ['primary_color', 'accent_color', 'sidebar_color']:
            value = request.POST.get(key, '')
            if value:
                SystemConfig.objects.update_or_create(
                    key=key, defaults={'value': value, 'description': f'Theme {key}'}
                )

        from django.contrib import messages as msg
        msg.success(request, 'Sistema personalizado exitosamente.')
        return redirect('system_customize')

    configs = {c.key: c.value for c in SystemConfig.objects.filter(key__in=['primary_color', 'accent_color', 'sidebar_color'])}

    return render(request, 'core/system_customize.html', {
        'company': company, 'configs': configs,
    })
