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

    # Sales stats (POS)
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

    # Sales module stats
    from apps.sales.models import SalesQuotation, SalesOrder, PickingOrder
    quotations_count = SalesQuotation.objects.filter(
        status__in=['draft', 'sent']
    ).count()
    quotations_accepted = SalesQuotation.objects.filter(
        status='accepted', created_at__date__gte=month_start
    ).count()
    orders_active = SalesOrder.objects.exclude(
        status__in=['cancelled', 'invoiced']
    ).count()
    orders_pending = SalesOrder.objects.filter(
        status__in=['confirmed', 'in_process']
    ).count()
    orders_total_value = SalesOrder.objects.exclude(
        status__in=['cancelled', 'draft']
    ).filter(
        created_at__date__gte=month_start
    ).aggregate(total=Sum('total'))['total'] or Decimal('0')
    picking_pending = PickingOrder.objects.filter(
        status__in=['pending', 'in_progress']
    ).count()

    # Manufacturing stats
    from apps.manufacturing.models import BillOfMaterials, ProductionOrder
    bom_count = BillOfMaterials.objects.filter(is_active=True).count()
    production_active = ProductionOrder.objects.filter(
        status__in=['confirmed', 'in_production', 'quality_check']
    ).count()
    production_completed_month = ProductionOrder.objects.filter(
        status='completed', end_date__date__gte=month_start
    ).count()

    # Logistics stats
    from apps.logistics.models import PurchaseOrder, Warehouse
    from apps.accounting.models import AccountReceivable, AccountPayable
    purchase_orders_pending = PurchaseOrder.objects.filter(
        status__in=['draft', 'confirmed', 'partial']
    ).count()
    total_products = Product.objects.filter(is_active=True).count()
    total_warehouses = Warehouse.objects.filter(is_active=True).count()

    # Finance stats
    receivable_total = AccountReceivable.objects.filter(
        status__in=['pending', 'partial', 'overdue']
    ).aggregate(total=Sum('total'), collected=Sum('collected_amount'))
    receivable_balance = (receivable_total['total'] or Decimal('0')) - (receivable_total['collected'] or Decimal('0'))
    payable_balance = AccountPayable.objects.filter(
        status__in=['pending', 'partial', 'overdue']
    ).aggregate(
        bal=Sum('total') - Sum('paid_amount')
    )['bal'] or Decimal('0')
    overdue_receivables = AccountReceivable.objects.filter(
        status='overdue'
    ).count()

    # Recent activity
    recent_orders = SalesOrder.objects.select_related('customer').order_by('-created_at')[:5]
    recent_quotations = SalesQuotation.objects.select_related('customer').order_by('-created_at')[:5]

    # Suppliers
    from apps.crm.models import Supplier
    total_suppliers = Supplier.objects.filter(is_active=True).count()

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
        # Sales module
        'quotations_count': quotations_count,
        'quotations_accepted': quotations_accepted,
        'orders_active': orders_active,
        'orders_pending': orders_pending,
        'orders_total_value': orders_total_value,
        'picking_pending': picking_pending,
        # Manufacturing
        'bom_count': bom_count,
        'production_active': production_active,
        'production_completed_month': production_completed_month,
        # Logistics
        'purchase_orders_pending': purchase_orders_pending,
        'total_products': total_products,
        'total_warehouses': total_warehouses,
        # Finance
        'receivable_balance': receivable_balance,
        'payable_balance': payable_balance,
        'overdue_receivables': overdue_receivables,
        # Activity
        'recent_orders': recent_orders,
        'recent_quotations': recent_quotations,
        # CRM
        'total_suppliers': total_suppliers,
    }
    return render(request, 'dashboard/dashboard.html', context)


def service_worker(request):
    """Serve service worker from root scope (Odoo-style controller pattern)."""
    return render(
        request,
        'pwa/service-worker.js',
        content_type='application/javascript; charset=utf-8',
    )


def pwa_manifest(request):
    """Dynamic manifest.webmanifest - Peru e-invoicing ERP (Odoo Enterprise pattern)."""
    import json
    from django.http import HttpResponse
    from apps.core.models import Company, SystemConfig

    company = Company.objects.first()
    configs = {c.key: c.value for c in SystemConfig.objects.filter(
        key__in=['primary_color', 'accent_color', 'pwa_short_name', 'pwa_theme_color', 'pwa_background_color']
    )}

    app_name = company.trade_name or company.name if company else 'NexusERP'
    short_name = configs.get('pwa_short_name', app_name[:12])
    theme_color = configs.get('pwa_theme_color', configs.get('primary_color', '#714B67'))
    bg_color = configs.get('pwa_background_color', '#0a0e1a')

    icons = []
    for size in [72, 96, 128, 144, 152, 192, 384, 512]:
        icons.append({
            'src': f'/static/pwa/icons/icon-{size}x{size}.png',
            'sizes': f'{size}x{size}',
            'type': 'image/png',
            'purpose': 'any maskable',
        })

    manifest = {
        'name': f'{app_name} - Facturacion Electronica',
        'short_name': short_name,
        'description': f'{app_name} - Sistema de Facturacion Electronica SUNAT Peru. '
                       f'Emite facturas, boletas, notas de credito, guias de remision.',
        'start_url': '/app/',
        'scope': '/',
        'display': 'standalone',
        'orientation': 'any',
        'background_color': bg_color,
        'theme_color': theme_color,
        'lang': 'es-PE',
        'dir': 'ltr',
        'categories': ['business', 'productivity', 'finance'],
        'icons': icons,
        'screenshots': [],
        'shortcuts': [
            {
                'name': 'Nueva Factura',
                'short_name': 'Factura',
                'description': 'Emitir factura electronica (01)',
                'url': '/accounting/invoices/new/?doc_type=01',
                'icons': [{'src': '/static/pwa/icons/icon-96x96.png', 'sizes': '96x96'}],
            },
            {
                'name': 'Nueva Boleta',
                'short_name': 'Boleta',
                'description': 'Emitir boleta de venta (03)',
                'url': '/accounting/invoices/new/?doc_type=03',
                'icons': [{'src': '/static/pwa/icons/icon-96x96.png', 'sizes': '96x96'}],
            },
            {
                'name': 'Punto de Venta',
                'short_name': 'POS',
                'description': 'Terminal de punto de venta con emision automatica',
                'url': '/pos/',
                'icons': [{'src': '/static/pwa/icons/icon-96x96.png', 'sizes': '96x96'}],
            },
            {
                'name': 'Consultar RUC',
                'short_name': 'RUC',
                'description': 'Consultar RUC en SUNAT',
                'url': '/sunat/consult-ruc/',
                'icons': [{'src': '/static/pwa/icons/icon-96x96.png', 'sizes': '96x96'}],
            },
        ],
        'related_applications': [],
        'prefer_related_applications': False,
    }

    return HttpResponse(
        json.dumps(manifest, ensure_ascii=False),
        content_type='application/manifest+json; charset=utf-8',
    )


def pwa_offline(request):
    """Offline fallback page."""
    return render(request, 'pwa/offline.html')


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
