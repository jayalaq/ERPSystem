from django.contrib.auth.decorators import login_required
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.db.models import Q, Sum, Count
from django.utils import timezone
from decimal import Decimal

from .models import (
    SalesQuotation, SalesQuotationItem,
    SalesOrder, SalesOrderItem,
    PickingOrder, PickingOrderItem,
)
from .forms import (
    SalesQuotationForm, SalesQuotationItemForm,
    SalesOrderForm, SalesOrderItemForm,
    PickingOrderForm,
)


# ============================================
# QUOTATIONS
# ============================================
@login_required
def quotation_list(request):
    quotations = SalesQuotation.objects.select_related('customer', 'created_by').order_by('-created_at')

    status_filter = request.GET.get('status', '')
    if status_filter:
        quotations = quotations.filter(status=status_filter)

    query = request.GET.get('q', '')
    if query:
        quotations = quotations.filter(
            Q(number__icontains=query) | Q(customer__name__icontains=query)
        )

    # Summary stats
    stats = {
        'total': quotations.count(),
        'draft': quotations.filter(status='draft').count(),
        'sent': quotations.filter(status='sent').count(),
        'accepted': quotations.filter(status='accepted').count(),
        'total_amount': quotations.filter(status__in=['sent', 'accepted']).aggregate(s=Sum('total'))['s'] or 0,
    }

    return render(request, 'sales/quotation_list.html', {
        'quotations': quotations[:100], 'stats': stats, 'query': query, 'status_filter': status_filter,
    })


@login_required
def quotation_create(request):
    if request.method == 'POST':
        form = SalesQuotationForm(request.POST)
        if form.is_valid():
            quotation = form.save(commit=False)
            quotation.created_by = request.user
            quotation.save()
            messages.success(request, f'Cotizacion {quotation.number} creada.')
            return redirect('sales:quotation_detail', pk=quotation.pk)
    else:
        # Auto-generate number
        last = SalesQuotation.objects.order_by('-id').first()
        next_num = f"COT-{(last.id + 1 if last else 1):04d}"
        form = SalesQuotationForm(initial={
            'number': next_num,
            'issue_date': timezone.now().date(),
            'valid_until': timezone.now().date() + timezone.timedelta(days=15),
            'status': 'draft',
        })
    return render(request, 'sales/quotation_form.html', {'form': form, 'title': 'Nueva Cotizacion'})


@login_required
def quotation_edit(request, pk):
    quotation = get_object_or_404(SalesQuotation, pk=pk)
    if request.method == 'POST':
        form = SalesQuotationForm(request.POST, instance=quotation)
        if form.is_valid():
            form.save()
            messages.success(request, 'Cotizacion actualizada.')
            return redirect('sales:quotation_detail', pk=quotation.pk)
    else:
        form = SalesQuotationForm(instance=quotation)
    return render(request, 'sales/quotation_form.html', {
        'form': form, 'title': f'Editar {quotation.number}', 'quotation': quotation,
    })


@login_required
def quotation_detail(request, pk):
    quotation = get_object_or_404(SalesQuotation.objects.select_related('customer', 'created_by'), pk=pk)
    items = quotation.items.select_related('product', 'unit')
    item_form = SalesQuotationItemForm()
    return render(request, 'sales/quotation_detail.html', {
        'quotation': quotation, 'items': items, 'item_form': item_form,
    })


@login_required
def quotation_add_item(request, pk):
    quotation = get_object_or_404(SalesQuotation, pk=pk)
    if request.method == 'POST':
        form = SalesQuotationItemForm(request.POST)
        if form.is_valid():
            item = form.save(commit=False)
            item.quotation = quotation
            if not item.description:
                item.description = item.product.name
            item.calculate_totals()
            item.save()
            quotation.recalculate_totals()
            messages.success(request, 'Item agregado.')
    return redirect('sales:quotation_detail', pk=pk)


@login_required
def quotation_remove_item(request, pk, item_pk):
    quotation = get_object_or_404(SalesQuotation, pk=pk)
    item = get_object_or_404(SalesQuotationItem, pk=item_pk, quotation=quotation)
    item.delete()
    quotation.recalculate_totals()
    messages.success(request, 'Item eliminado.')
    return redirect('sales:quotation_detail', pk=pk)


@login_required
def quotation_convert_to_order(request, pk):
    """Convert an accepted quotation to a sales order."""
    quotation = get_object_or_404(SalesQuotation, pk=pk)

    if quotation.sales_order:
        messages.warning(request, f'Esta cotizacion ya tiene el pedido {quotation.sales_order.number}.')
        return redirect('sales:quotation_detail', pk=pk)

    from apps.logistics.models import Warehouse
    warehouse = Warehouse.objects.filter(is_active=True, is_default=True).first()
    if not warehouse:
        warehouse = Warehouse.objects.filter(is_active=True).first()

    if not warehouse:
        messages.error(request, 'No hay almacenes activos. Cree uno primero.')
        return redirect('sales:quotation_detail', pk=pk)

    # Create sales order
    last_order = SalesOrder.objects.order_by('-id').first()
    order_number = f"PED-{(last_order.id + 1 if last_order else 1):04d}"

    order = SalesOrder.objects.create(
        number=order_number,
        customer=quotation.customer,
        warehouse=warehouse,
        status='draft',
        priority='normal',
        order_date=timezone.now().date(),
        expected_date=quotation.valid_until,
        payment_terms=quotation.payment_terms,
        delivery_terms=quotation.delivery_terms if hasattr(quotation, 'delivery_terms') else '',
        subtotal=quotation.subtotal,
        discount_amount=quotation.discount_amount,
        igv=quotation.igv,
        total=quotation.total,
        notes=quotation.notes,
        created_by=request.user,
    )

    # Copy items
    for q_item in quotation.items.all():
        SalesOrderItem.objects.create(
            order=order,
            product=q_item.product,
            description=q_item.description,
            quantity=q_item.quantity,
            unit=q_item.unit,
            unit_price=q_item.unit_price,
            discount=q_item.discount,
            affectation_type=q_item.affectation_type,
            igv=q_item.igv,
            subtotal=q_item.subtotal,
            total=q_item.total,
        )

    # Update quotation
    quotation.sales_order = order
    quotation.status = 'accepted'
    quotation.save(update_fields=['sales_order', 'status'])

    messages.success(request, f'Pedido {order.number} creado desde cotizacion {quotation.number}.')
    return redirect('sales:order_detail', pk=order.pk)


# ============================================
# SALES ORDERS
# ============================================
@login_required
def order_list(request):
    orders = SalesOrder.objects.select_related('customer', 'warehouse', 'created_by').order_by('-created_at')

    status_filter = request.GET.get('status', '')
    if status_filter:
        orders = orders.filter(status=status_filter)

    query = request.GET.get('q', '')
    if query:
        orders = orders.filter(
            Q(number__icontains=query) | Q(customer__name__icontains=query)
        )

    stats = {
        'total': orders.count(),
        'confirmed': orders.filter(status='confirmed').count(),
        'in_process': orders.filter(status='in_process').count(),
        'delivered': orders.filter(status='delivered').count(),
        'total_amount': orders.filter(
            status__in=['confirmed', 'in_process', 'ready', 'dispatched', 'delivered', 'invoiced']
        ).aggregate(s=Sum('total'))['s'] or 0,
    }

    return render(request, 'sales/order_list.html', {
        'orders': orders[:100], 'stats': stats, 'query': query, 'status_filter': status_filter,
    })


@login_required
def order_create(request):
    if request.method == 'POST':
        form = SalesOrderForm(request.POST)
        if form.is_valid():
            order = form.save(commit=False)
            order.created_by = request.user
            order.save()
            messages.success(request, f'Pedido {order.number} creado.')
            return redirect('sales:order_detail', pk=order.pk)
    else:
        last = SalesOrder.objects.order_by('-id').first()
        next_num = f"PED-{(last.id + 1 if last else 1):04d}"
        form = SalesOrderForm(initial={
            'number': next_num,
            'order_date': timezone.now().date(),
            'status': 'draft',
            'priority': 'normal',
        })
    return render(request, 'sales/order_form.html', {'form': form, 'title': 'Nuevo Pedido de Venta'})


@login_required
def order_edit(request, pk):
    order = get_object_or_404(SalesOrder, pk=pk)
    if request.method == 'POST':
        form = SalesOrderForm(request.POST, instance=order)
        if form.is_valid():
            form.save()
            messages.success(request, 'Pedido actualizado.')
            return redirect('sales:order_detail', pk=order.pk)
    else:
        form = SalesOrderForm(instance=order)
    return render(request, 'sales/order_form.html', {
        'form': form, 'title': f'Editar {order.number}', 'order': order,
    })


@login_required
def order_detail(request, pk):
    order = get_object_or_404(SalesOrder.objects.select_related('customer', 'warehouse', 'created_by'), pk=pk)
    items = order.items.select_related('product', 'unit')
    picking_orders = order.picking_orders.select_related('assigned_to', 'warehouse')
    item_form = SalesOrderItemForm()
    return render(request, 'sales/order_detail.html', {
        'order': order, 'items': items, 'picking_orders': picking_orders, 'item_form': item_form,
    })


@login_required
def order_add_item(request, pk):
    order = get_object_or_404(SalesOrder, pk=pk)
    if request.method == 'POST':
        form = SalesOrderItemForm(request.POST)
        if form.is_valid():
            item = form.save(commit=False)
            item.order = order
            if not item.description:
                item.description = item.product.name
            item.calculate_totals()
            item.save()
            order.recalculate_totals()
            messages.success(request, 'Item agregado.')
    return redirect('sales:order_detail', pk=pk)


@login_required
def order_remove_item(request, pk, item_pk):
    order = get_object_or_404(SalesOrder, pk=pk)
    item = get_object_or_404(SalesOrderItem, pk=item_pk, order=order)
    item.delete()
    order.recalculate_totals()
    messages.success(request, 'Item eliminado.')
    return redirect('sales:order_detail', pk=pk)


@login_required
def order_confirm(request, pk):
    """Confirm a sales order - reserves stock."""
    order = get_object_or_404(SalesOrder, pk=pk)
    if order.status != 'draft':
        messages.warning(request, 'Solo se pueden confirmar pedidos en borrador.')
        return redirect('sales:order_detail', pk=pk)

    if not order.items.exists():
        messages.error(request, 'El pedido no tiene items.')
        return redirect('sales:order_detail', pk=pk)

    # Reserve stock
    from apps.logistics.models import StockLevel
    stock_issues = []
    for item in order.items.all():
        if item.product.track_inventory:
            stock = StockLevel.objects.filter(
                product=item.product, warehouse=order.warehouse
            ).first()
            available = stock.available if stock else 0
            if available < item.quantity:
                stock_issues.append(f"{item.product.name}: disponible {available}, solicitado {item.quantity}")

    if stock_issues:
        messages.warning(request, 'Stock insuficiente: ' + '; '.join(stock_issues))

    # Reserve stock for items with availability
    for item in order.items.all():
        if item.product.track_inventory:
            stock, _ = StockLevel.objects.get_or_create(
                product=item.product, warehouse=order.warehouse,
                defaults={'quantity': 0, 'reserved': 0}
            )
            stock.reserved += item.quantity
            stock.save(update_fields=['reserved'])

    order.status = 'confirmed'
    order.save(update_fields=['status'])
    messages.success(request, f'Pedido {order.number} confirmado.')
    return redirect('sales:order_detail', pk=pk)


@login_required
def order_generate_picking(request, pk):
    """Generate a picking order for a sales order."""
    order = get_object_or_404(SalesOrder, pk=pk)
    if order.status not in ('confirmed', 'in_process'):
        messages.warning(request, 'El pedido debe estar confirmado para generar picking.')
        return redirect('sales:order_detail', pk=pk)

    last_pick = PickingOrder.objects.order_by('-id').first()
    pick_number = f"PICK-{(last_pick.id + 1 if last_pick else 1):04d}"

    picking = PickingOrder.objects.create(
        number=pick_number,
        sales_order=order,
        warehouse=order.warehouse,
        status='pending',
        scheduled_date=timezone.now().date(),
        created_by=request.user,
    )

    for item in order.items.all():
        pending = item.pending_quantity
        if pending > 0:
            PickingOrderItem.objects.create(
                picking_order=picking,
                product=item.product,
                quantity_requested=pending,
            )

    order.status = 'in_process'
    order.save(update_fields=['status'])

    messages.success(request, f'Orden de picking {picking.number} generada.')
    return redirect('sales:picking_detail', pk=picking.pk)


# ============================================
# PICKING ORDERS
# ============================================
@login_required
def picking_list(request):
    pickings = PickingOrder.objects.select_related(
        'sales_order', 'warehouse', 'assigned_to'
    ).order_by('-created_at')

    status_filter = request.GET.get('status', '')
    if status_filter:
        pickings = pickings.filter(status=status_filter)

    stats = {
        'total': pickings.count(),
        'pending': pickings.filter(status='pending').count(),
        'in_progress': pickings.filter(status='in_progress').count(),
        'completed': pickings.filter(status='completed').count(),
    }

    return render(request, 'sales/picking_list.html', {
        'pickings': pickings[:100], 'stats': stats, 'status_filter': status_filter,
    })


@login_required
def picking_detail(request, pk):
    picking = get_object_or_404(
        PickingOrder.objects.select_related('sales_order', 'warehouse', 'assigned_to'), pk=pk
    )
    items = picking.items.select_related('product')
    return render(request, 'sales/picking_detail.html', {'picking': picking, 'items': items})


@login_required
def picking_start(request, pk):
    picking = get_object_or_404(PickingOrder, pk=pk)
    if picking.status == 'pending':
        picking.status = 'in_progress'
        picking.started_at = timezone.now()
        if not picking.assigned_to:
            picking.assigned_to = request.user
        picking.save(update_fields=['status', 'started_at', 'assigned_to'])
        messages.success(request, 'Picking iniciado.')
    return redirect('sales:picking_detail', pk=pk)


@login_required
def picking_pick_item(request, pk, item_pk):
    """Mark an item as picked."""
    picking = get_object_or_404(PickingOrder, pk=pk)
    item = get_object_or_404(PickingOrderItem, pk=item_pk, picking_order=picking)

    if request.method == 'POST':
        qty = request.POST.get('quantity_picked', item.quantity_requested)
        item.quantity_picked = Decimal(str(qty))
        item.picked = True
        item.picked_by = request.user
        item.picked_at = timezone.now()
        item.save()

        # Check if all items are picked
        all_picked = not picking.items.filter(picked=False).exists()
        if all_picked:
            picking.status = 'completed'
            picking.completed_at = timezone.now()
            picking.save(update_fields=['status', 'completed_at'])

            # Update sales order
            order = picking.sales_order
            order.status = 'ready'
            order.save(update_fields=['status'])

            # Create stock movements
            from apps.logistics.models import StockMovement, StockLevel
            for p_item in picking.items.all():
                StockMovement.objects.create(
                    movement_type='out',
                    product=p_item.product,
                    warehouse=picking.warehouse,
                    quantity=p_item.quantity_picked,
                    reference=f"Picking {picking.number}",
                    reference_type='picking',
                    reference_id=picking.pk,
                    reason=f"Despacho pedido {order.number}",
                    performed_by=request.user,
                )
                # Update stock
                stock, _ = StockLevel.objects.get_or_create(
                    product=p_item.product, warehouse=picking.warehouse,
                    defaults={'quantity': 0, 'reserved': 0}
                )
                stock.quantity -= p_item.quantity_picked
                stock.reserved = max(0, stock.reserved - p_item.quantity_picked)
                stock.save(update_fields=['quantity', 'reserved'])

            messages.success(request, f'Picking {picking.number} completado. Pedido listo para despacho.')
        else:
            messages.success(request, f'Item {item.product.name} preparado.')

    return redirect('sales:picking_detail', pk=pk)
