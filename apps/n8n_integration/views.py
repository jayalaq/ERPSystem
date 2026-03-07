"""
n8n Integration API Views.
Provides endpoints for n8n to interact with the ERP:
  - Receive actions (create customers, products, invoices, etc.)
  - Query data (customers, products, stock, sales, etc.)
  - Trigger SUNAT operations
"""
import json
import hmac
import hashlib
import logging

from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST, require_GET
from django.conf import settings
from django.db.models import Sum, Count, Q, F
from django.utils import timezone
from decimal import Decimal

from .services import N8nActionProcessor, DecimalEncoder
from .models import N8nWebhook, N8nEventLog, N8nIncomingAction

logger = logging.getLogger(__name__)


def verify_n8n_auth(request):
    """Verify n8n request authentication via API key or HMAC."""
    api_key = request.headers.get('X-N8N-API-Key', '')
    expected_key = getattr(settings, 'N8N_API_KEY', '') or ''

    if not expected_key:
        return True  # No key configured, allow (development)

    if api_key == expected_key:
        return True

    # Check HMAC signature
    signature = request.headers.get('X-N8N-Signature', '')
    if signature and expected_key:
        expected = hmac.new(
            expected_key.encode(), request.body, hashlib.sha256
        ).hexdigest()
        return hmac.compare_digest(signature, f"sha256={expected}")

    return False


def n8n_response(data, status=200):
    """Standard JSON response with Decimal support."""
    return JsonResponse(data, status=status, encoder=DecimalEncoder, safe=False)


# ============================================
# INCOMING ACTIONS FROM n8n
# ============================================
@csrf_exempt
@require_POST
def n8n_action(request):
    """
    Main endpoint for n8n to execute actions in the ERP.
    POST /api/n8n/action/

    Body: {
        "action": "create_customer|update_stock|create_invoice|...",
        "data": { ... action-specific data ... },
        "execution_id": "optional-n8n-execution-id"
    }
    """
    if not verify_n8n_auth(request):
        return n8n_response({'error': 'Unauthorized'}, 401)

    try:
        body = json.loads(request.body)
    except json.JSONDecodeError:
        return n8n_response({'error': 'Invalid JSON'}, 400)

    action_type = body.get('action')
    data = body.get('data', {})
    execution_id = body.get('execution_id', '')

    if not action_type:
        return n8n_response({'error': 'Missing "action" field'}, 400)

    result = N8nActionProcessor.process(action_type, data, execution_id)
    status = 200 if result.get('success') else 400
    return n8n_response(result, status)


# ============================================
# DATA QUERIES FOR n8n
# ============================================
@csrf_exempt
@require_GET
def n8n_customers(request):
    """GET /api/n8n/customers/ - Query customers for n8n workflows."""
    if not verify_n8n_auth(request):
        return n8n_response({'error': 'Unauthorized'}, 401)

    from apps.crm.models import Customer

    q = request.GET.get('q', '')
    doc_number = request.GET.get('doc_number', '')
    limit = min(int(request.GET.get('limit', 50)), 200)

    customers = Customer.objects.filter(is_active=True)
    if doc_number:
        customers = customers.filter(doc_number=doc_number)
    elif q:
        customers = customers.filter(
            Q(name__icontains=q) | Q(doc_number__icontains=q) | Q(email__icontains=q)
        )

    data = list(customers[:limit].values(
        'id', 'doc_type', 'doc_number', 'name', 'customer_type',
        'email', 'phone', 'address', 'credit_limit', 'credit_days',
    ))
    return n8n_response({'customers': data, 'count': len(data)})


@csrf_exempt
@require_GET
def n8n_products(request):
    """GET /api/n8n/products/ - Query products for n8n workflows."""
    if not verify_n8n_auth(request):
        return n8n_response({'error': 'Unauthorized'}, 401)

    from apps.logistics.models import Product

    q = request.GET.get('q', '')
    sku = request.GET.get('sku', '')
    category = request.GET.get('category', '')
    low_stock = request.GET.get('low_stock', '')
    limit = min(int(request.GET.get('limit', 50)), 200)

    products = Product.objects.filter(is_active=True).select_related('category', 'unit')
    if sku:
        products = products.filter(sku=sku)
    elif q:
        products = products.filter(Q(name__icontains=q) | Q(sku__icontains=q) | Q(barcode__icontains=q))
    if category:
        products = products.filter(category__slug=category)
    if low_stock:
        products = products.annotate(
            current_stock=Sum('stock_levels__quantity')
        ).filter(current_stock__lte=F('min_stock'))

    data = []
    for p in products[:limit]:
        data.append({
            'id': p.pk, 'sku': p.sku, 'name': p.name,
            'category': p.category.name if p.category else '',
            'sale_price': float(p.sale_price),
            'purchase_price': float(p.purchase_price),
            'unit': p.unit.abbreviation if p.unit else 'UND',
            'total_stock': float(p.total_stock),
            'min_stock': float(p.min_stock),
            'product_type': p.product_type,
        })
    return n8n_response({'products': data, 'count': len(data)})


@csrf_exempt
@require_GET
def n8n_stock(request):
    """GET /api/n8n/stock/ - Query stock levels."""
    if not verify_n8n_auth(request):
        return n8n_response({'error': 'Unauthorized'}, 401)

    from apps.logistics.models import StockLevel

    warehouse = request.GET.get('warehouse', '')
    sku = request.GET.get('sku', '')

    levels = StockLevel.objects.select_related('product', 'warehouse')
    if warehouse:
        levels = levels.filter(warehouse__code=warehouse)
    if sku:
        levels = levels.filter(product__sku=sku)

    data = list(levels.values(
        'product__sku', 'product__name', 'warehouse__code', 'warehouse__name',
        'quantity', 'reserved',
    )[:200])
    return n8n_response({'stock': data, 'count': len(data)})


@csrf_exempt
@require_GET
def n8n_sales(request):
    """GET /api/n8n/sales/ - Query POS sales."""
    if not verify_n8n_auth(request):
        return n8n_response({'error': 'Unauthorized'}, 401)

    from apps.pos.models import POSSale

    date_from = request.GET.get('from', '')
    date_to = request.GET.get('to', '')
    status = request.GET.get('status', 'completed')
    limit = min(int(request.GET.get('limit', 50)), 200)

    sales = POSSale.objects.filter(status=status).select_related('customer', 'seller')
    if date_from:
        sales = sales.filter(created_at__date__gte=date_from)
    if date_to:
        sales = sales.filter(created_at__date__lte=date_to)

    data = []
    for s in sales.order_by('-created_at')[:limit]:
        data.append({
            'id': s.pk, 'uuid': str(s.uuid),
            'number': f"{s.series}-{s.correlative}",
            'doc_type': s.doc_type,
            'customer': s.customer.name if s.customer else 'Varios',
            'payment_method': s.payment_method,
            'subtotal': float(s.subtotal), 'igv': float(s.igv),
            'total': float(s.total), 'status': s.status,
            'seller': s.seller.get_full_name() if s.seller else '',
            'created_at': s.created_at.isoformat(),
        })
    return n8n_response({'sales': data, 'count': len(data)})


@csrf_exempt
@require_GET
def n8n_invoices(request):
    """GET /api/n8n/invoices/ - Query invoices."""
    if not verify_n8n_auth(request):
        return n8n_response({'error': 'Unauthorized'}, 401)

    from apps.accounting.models import Invoice

    status = request.GET.get('status', '')
    date_from = request.GET.get('from', '')
    limit = min(int(request.GET.get('limit', 50)), 200)

    invoices = Invoice.objects.select_related('customer')
    if status:
        invoices = invoices.filter(status=status)
    if date_from:
        invoices = invoices.filter(created_at__date__gte=date_from)

    data = []
    for inv in invoices.order_by('-created_at')[:limit]:
        data.append({
            'id': inv.pk, 'number': inv.full_number,
            'doc_type': inv.get_doc_type_display(),
            'customer': inv.customer.name,
            'customer_ruc': inv.customer.doc_number,
            'total': float(inv.total), 'igv': float(inv.igv),
            'status': inv.status,
            'sunat_response': inv.sunat_response_code,
            'issue_date': inv.issue_date.isoformat(),
        })
    return n8n_response({'invoices': data, 'count': len(data)})


@csrf_exempt
@require_GET
def n8n_dashboard(request):
    """GET /api/n8n/dashboard/ - Business summary for n8n dashboards."""
    if not verify_n8n_auth(request):
        return n8n_response({'error': 'Unauthorized'}, 401)

    from apps.pos.models import POSSale
    from apps.crm.models import Customer, Opportunity
    from apps.accounting.models import Invoice, AccountPayable
    from apps.logistics.models import Product, StockLevel

    today = timezone.now().date()
    month_start = today.replace(day=1)

    today_sales = POSSale.objects.filter(
        created_at__date=today, status='completed'
    ).aggregate(count=Count('id'), total=Sum('total'))

    monthly_sales = POSSale.objects.filter(
        created_at__date__gte=month_start, status='completed'
    ).aggregate(count=Count('id'), total=Sum('total'))

    pipeline = Opportunity.objects.exclude(
        stage__in=['closed_won', 'closed_lost']
    ).aggregate(count=Count('id'), total=Sum('expected_amount'))

    overdue_payables = AccountPayable.objects.filter(
        status__in=['pending', 'overdue'], due_date__lt=today
    ).aggregate(count=Count('id'), total=Sum('total'))

    low_stock = Product.objects.filter(
        track_inventory=True, is_active=True
    ).annotate(
        current_stock=Sum('stock_levels__quantity')
    ).filter(current_stock__lte=F('min_stock')).count()

    return n8n_response({
        'date': today.isoformat(),
        'today_sales': {
            'count': today_sales['count'] or 0,
            'total': float(today_sales['total'] or 0),
        },
        'monthly_sales': {
            'count': monthly_sales['count'] or 0,
            'total': float(monthly_sales['total'] or 0),
        },
        'crm': {
            'total_customers': Customer.objects.filter(is_active=True).count(),
            'pipeline_count': pipeline['count'] or 0,
            'pipeline_value': float(pipeline['total'] or 0),
        },
        'overdue_payables': {
            'count': overdue_payables['count'] or 0,
            'total': float(overdue_payables['total'] or 0),
        },
        'low_stock_products': low_stock,
        'pending_invoices': Invoice.objects.filter(status='draft').count(),
    })


@csrf_exempt
@require_GET
def n8n_opportunities(request):
    """GET /api/n8n/opportunities/ - Query CRM opportunities."""
    if not verify_n8n_auth(request):
        return n8n_response({'error': 'Unauthorized'}, 401)

    from apps.crm.models import Opportunity

    stage = request.GET.get('stage', '')
    opportunities = Opportunity.objects.select_related('customer', 'assigned_to')
    if stage:
        opportunities = opportunities.filter(stage=stage)

    data = []
    for opp in opportunities[:100]:
        data.append({
            'id': opp.pk, 'title': opp.title,
            'customer': opp.customer.name,
            'stage': opp.stage, 'priority': opp.priority,
            'expected_amount': float(opp.expected_amount),
            'probability': opp.probability,
            'weighted_amount': float(opp.weighted_amount),
            'assigned_to': opp.assigned_to.get_full_name() if opp.assigned_to else '',
            'expected_close_date': opp.expected_close_date.isoformat() if opp.expected_close_date else '',
        })
    return n8n_response({'opportunities': data, 'count': len(data)})


@csrf_exempt
@require_GET
def n8n_event_logs(request):
    """GET /api/n8n/logs/ - View recent webhook delivery logs."""
    if not verify_n8n_auth(request):
        return n8n_response({'error': 'Unauthorized'}, 401)

    limit = min(int(request.GET.get('limit', 50)), 200)
    status = request.GET.get('status', '')

    logs = N8nEventLog.objects.select_related('webhook')
    if status:
        logs = logs.filter(status=status)

    data = list(logs[:limit].values(
        'id', 'event_type', 'status', 'response_code',
        'error_message', 'attempts', 'created_at', 'sent_at',
    ))
    return n8n_response({'logs': data, 'count': len(data)})
