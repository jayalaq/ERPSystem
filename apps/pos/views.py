import json
from decimal import Decimal

from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.utils import timezone
from django.views.decorators.http import require_POST
from django.db import transaction
from django.db.models import Sum, Q

from .models import CashRegister, CashSession, POSSale, POSSaleItem, PaymentDetail
from apps.crm.models import Customer
from apps.logistics.models import Product, StockLevel, StockMovement
from apps.accounting.models import DocumentSeries


@login_required
def pos_terminal(request):
    """Main POS terminal view."""
    session = CashSession.objects.filter(user=request.user, status='open').first()
    if not session:
        return redirect('pos:open_session')

    products = Product.objects.filter(is_active=True).select_related('category', 'unit')
    categories = set(p.category for p in products if p.category)

    return render(request, 'pos/terminal.html', {
        'session': session,
        'products': products,
        'categories': categories,
    })


@login_required
def open_session(request):
    """Open a new cash register session."""
    existing = CashSession.objects.filter(user=request.user, status='open').first()
    if existing:
        return redirect('pos:terminal')

    registers = CashRegister.objects.filter(is_active=True)
    if request.method == 'POST':
        register_id = request.POST.get('register')
        opening_amount = request.POST.get('opening_amount', '0')
        register = get_object_or_404(CashRegister, pk=register_id)
        CashSession.objects.create(
            cash_register=register,
            user=request.user,
            opening_amount=Decimal(opening_amount),
        )
        messages.success(request, 'Sesión de caja abierta.')
        return redirect('pos:terminal')
    return render(request, 'pos/open_session.html', {'registers': registers})


@login_required
@require_POST
def close_session(request):
    """Close current cash session."""
    session = get_object_or_404(CashSession, user=request.user, status='open')
    closing_amount = Decimal(request.POST.get('closing_amount', '0'))

    sales = session.sales.filter(status='completed')
    total_sales = sales.aggregate(t=Sum('total'))['t'] or Decimal('0')
    total_cash = sales.filter(payment_method='cash').aggregate(t=Sum('total'))['t'] or Decimal('0')
    total_card = sales.filter(payment_method='card').aggregate(t=Sum('total'))['t'] or Decimal('0')
    total_transfer = sales.filter(payment_method__in=['transfer', 'yape', 'plin']).aggregate(t=Sum('total'))['t'] or Decimal('0')

    expected = session.opening_amount + total_cash
    session.closing_amount = closing_amount
    session.expected_amount = expected
    session.difference = closing_amount - expected
    session.total_sales = total_sales
    session.total_cash = total_cash
    session.total_card = total_card
    session.total_transfer = total_transfer
    session.status = 'closed'
    session.closed_at = timezone.now()
    session.notes = request.POST.get('notes', '')
    session.save()

    messages.success(request, f'Sesión cerrada. Diferencia: S/ {session.difference}')
    return redirect('pos:session_summary', pk=session.pk)


@login_required
def session_summary(request, pk):
    session = get_object_or_404(CashSession, pk=pk)
    sales = session.sales.filter(status='completed')
    return render(request, 'pos/session_summary.html', {'session': session, 'sales': sales})


@login_required
@require_POST
def process_sale(request):
    """Process a POS sale transaction."""
    session = get_object_or_404(CashSession, user=request.user, status='open')

    try:
        data = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({'success': False, 'message': 'Datos inválidos'})

    items_data = data.get('items', [])
    if not items_data:
        return JsonResponse({'success': False, 'message': 'No hay productos en la venta'})

    doc_type = data.get('doc_type', 'boleta')
    payment_method = data.get('payment_method', 'cash')
    customer_id = data.get('customer_id')
    amount_received = Decimal(str(data.get('amount_received', 0)))

    # Get document series
    series_map = {'boleta': '03', 'factura': '01', 'nota_venta': 'NV', 'ticket': 'TK'}
    sunat_doc_type = series_map.get(doc_type, '03')
    doc_series = DocumentSeries.objects.filter(
        doc_type=sunat_doc_type, is_active=True, branch=session.cash_register.branch
    ).first()

    if not doc_series and doc_type in ('boleta', 'factura'):
        return JsonResponse({'success': False, 'message': 'No se encontró serie de documento configurada'})

    with transaction.atomic():
        subtotal = Decimal('0')
        igv_total = Decimal('0')
        discount_total = Decimal(str(data.get('discount', 0)))

        # Calculate totals
        sale_items = []
        for item_data in items_data:
            product = Product.objects.select_for_update().get(pk=item_data['product_id'])
            qty = Decimal(str(item_data['quantity']))
            price = Decimal(str(item_data.get('price', product.sale_price)))
            item_discount = Decimal(str(item_data.get('discount', 0)))

            item_subtotal = (price * qty) - item_discount
            if product.affectation_type == '10':
                item_igv = item_subtotal * Decimal('0.18')
            else:
                item_igv = Decimal('0')
            item_total = item_subtotal + item_igv

            subtotal += item_subtotal
            igv_total += item_igv

            sale_items.append({
                'product': product,
                'quantity': qty,
                'unit_price': price,
                'discount': item_discount,
                'subtotal': item_subtotal,
                'igv': item_igv,
                'total': item_total,
            })

        total = subtotal + igv_total - discount_total
        change = amount_received - total if payment_method == 'cash' else Decimal('0')

        # Get correlative
        if doc_series:
            series_code = doc_series.series
            correlative = str(doc_series.get_next_number()).zfill(8)
        else:
            series_code = 'NV01'
            from apps.pos.models import POSSale as PS
            last = PS.objects.filter(series=series_code).order_by('-correlative').first()
            correlative = str(int(last.correlative) + 1).zfill(8) if last else '00000001'

        customer = None
        if customer_id:
            customer = Customer.objects.filter(pk=customer_id).first()

        sale = POSSale.objects.create(
            session=session,
            customer=customer,
            doc_type=doc_type,
            series=series_code,
            correlative=correlative,
            payment_method=payment_method,
            subtotal=subtotal,
            discount=discount_total,
            igv=igv_total,
            total=total,
            amount_received=amount_received,
            change_amount=max(change, Decimal('0')),
            seller=request.user,
        )

        # Create sale items and update stock
        for item in sale_items:
            POSSaleItem.objects.create(sale=sale, **item)

            if item['product'].track_inventory:
                warehouse = session.cash_register.branch.warehouses.filter(is_default=True).first()
                if warehouse:
                    stock, _ = StockLevel.objects.get_or_create(
                        product=item['product'], warehouse=warehouse,
                        defaults={'quantity': 0}
                    )
                    stock.quantity -= item['quantity']
                    stock.save()

                    StockMovement.objects.create(
                        movement_type='out',
                        product=item['product'],
                        warehouse=warehouse,
                        quantity=item['quantity'],
                        reference=f"POS-{sale.series}-{sale.correlative}",
                        reference_type='pos_sale',
                        reference_id=sale.pk,
                        performed_by=request.user,
                    )

        # Payment details for mixed payments
        payments = data.get('payments', [])
        for payment in payments:
            PaymentDetail.objects.create(
                sale=sale,
                method=payment['method'],
                amount=Decimal(str(payment['amount'])),
                reference=payment.get('reference', ''),
            )

    return JsonResponse({
        'success': True,
        'sale_id': sale.pk,
        'sale_uuid': str(sale.uuid),
        'number': f"{sale.series}-{sale.correlative}",
        'total': str(total),
        'change': str(max(change, Decimal('0'))),
    })


@login_required
def sale_receipt(request, pk):
    """View/print sale receipt."""
    sale = get_object_or_404(POSSale, pk=pk)
    return render(request, 'pos/receipt.html', {'sale': sale})


@login_required
def sales_history(request):
    """View POS sales history."""
    sales = POSSale.objects.select_related('customer', 'seller', 'session__cash_register').order_by('-created_at')
    date_from = request.GET.get('from')
    date_to = request.GET.get('to')
    if date_from:
        sales = sales.filter(created_at__date__gte=date_from)
    if date_to:
        sales = sales.filter(created_at__date__lte=date_to)
    return render(request, 'pos/sales_history.html', {'sales': sales[:100]})


@login_required
def product_search(request):
    """AJAX product search for POS terminal."""
    q = request.GET.get('q', '')
    products = Product.objects.filter(
        is_active=True
    ).filter(
        Q(name__icontains=q) | Q(sku__icontains=q) | Q(barcode__icontains=q)
    )[:20]

    results = [{
        'id': p.id,
        'sku': p.sku,
        'name': p.name,
        'price': str(p.sale_price),
        'stock': str(p.total_stock),
        'unit': p.unit.abbreviation if p.unit else 'UND',
        'image': p.image.url if p.image else '',
    } for p in products]

    return JsonResponse({'products': results})
