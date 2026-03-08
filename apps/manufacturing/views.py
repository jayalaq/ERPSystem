from django.contrib.auth.decorators import login_required
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.db.models import Q, Sum
from django.utils import timezone
from decimal import Decimal

from .models import BillOfMaterials, BOMComponent, ProductionOrder, ProductionOrderComponent
from .forms import BOMForm, BOMComponentForm, ProductionOrderForm


# ============================================
# BILL OF MATERIALS
# ============================================
@login_required
def bom_list(request):
    boms = BillOfMaterials.objects.select_related('product', 'product__unit').filter(is_active=True)

    query = request.GET.get('q', '')
    if query:
        boms = boms.filter(Q(product__name__icontains=query) | Q(name__icontains=query))

    return render(request, 'manufacturing/bom_list.html', {'boms': boms, 'query': query})


@login_required
def bom_create(request):
    if request.method == 'POST':
        form = BOMForm(request.POST)
        if form.is_valid():
            bom = form.save(commit=False)
            bom.created_by = request.user
            bom.save()
            messages.success(request, f'Lista de Materiales creada para {bom.product.name}.')
            return redirect('manufacturing:bom_detail', pk=bom.pk)
    else:
        form = BOMForm()
    return render(request, 'manufacturing/bom_form.html', {'form': form, 'title': 'Nueva Lista de Materiales'})


@login_required
def bom_edit(request, pk):
    bom = get_object_or_404(BillOfMaterials, pk=pk)
    if request.method == 'POST':
        form = BOMForm(request.POST, instance=bom)
        if form.is_valid():
            form.save()
            messages.success(request, 'Lista de Materiales actualizada.')
            return redirect('manufacturing:bom_detail', pk=bom.pk)
    else:
        form = BOMForm(instance=bom)
    return render(request, 'manufacturing/bom_form.html', {'form': form, 'title': f'Editar BOM: {bom.product.name}', 'bom': bom})


@login_required
def bom_detail(request, pk):
    bom = get_object_or_404(BillOfMaterials.objects.select_related('product', 'created_by'), pk=pk)
    components = bom.components.select_related('component', 'unit')
    component_form = BOMComponentForm()
    return render(request, 'manufacturing/bom_detail.html', {
        'bom': bom, 'components': components, 'component_form': component_form,
    })


@login_required
def bom_add_component(request, pk):
    bom = get_object_or_404(BillOfMaterials, pk=pk)
    if request.method == 'POST':
        form = BOMComponentForm(request.POST)
        if form.is_valid():
            comp = form.save(commit=False)
            comp.bom = bom
            comp.save()
            bom.calculate_cost()
            messages.success(request, f'Componente {comp.component.name} agregado.')
    return redirect('manufacturing:bom_detail', pk=pk)


@login_required
def bom_remove_component(request, pk, comp_pk):
    bom = get_object_or_404(BillOfMaterials, pk=pk)
    comp = get_object_or_404(BOMComponent, pk=comp_pk, bom=bom)
    comp.delete()
    bom.calculate_cost()
    messages.success(request, 'Componente eliminado.')
    return redirect('manufacturing:bom_detail', pk=pk)


# ============================================
# PRODUCTION ORDERS
# ============================================
@login_required
def production_order_list(request):
    orders = ProductionOrder.objects.select_related('product', 'bom', 'warehouse', 'created_by').order_by('-created_at')

    status_filter = request.GET.get('status', '')
    if status_filter:
        orders = orders.filter(status=status_filter)

    query = request.GET.get('q', '')
    if query:
        orders = orders.filter(Q(number__icontains=query) | Q(product__name__icontains=query))

    stats = {
        'total': orders.count(),
        'confirmed': orders.filter(status='confirmed').count(),
        'in_production': orders.filter(status='in_production').count(),
        'completed': orders.filter(status='completed').count(),
    }

    return render(request, 'manufacturing/production_order_list.html', {
        'orders': orders[:100], 'stats': stats, 'query': query, 'status_filter': status_filter,
    })


@login_required
def production_order_create(request):
    if request.method == 'POST':
        form = ProductionOrderForm(request.POST)
        if form.is_valid():
            order = form.save(commit=False)
            order.status = 'draft'
            order.created_by = request.user
            # Calculate estimated cost
            order.estimated_cost = order.bom.estimated_cost * (order.quantity / order.bom.quantity)
            order.save()

            # Create component lines from BOM
            for bom_comp in order.bom.components.all():
                qty = bom_comp.quantity * (order.quantity / order.bom.quantity)
                ProductionOrderComponent.objects.create(
                    production_order=order,
                    component=bom_comp.component,
                    quantity_required=qty,
                    unit=bom_comp.unit,
                )

            messages.success(request, f'Orden de Produccion {order.number} creada.')
            return redirect('manufacturing:production_order_detail', pk=order.pk)
    else:
        last = ProductionOrder.objects.order_by('-id').first()
        next_num = f"OP-{(last.id + 1 if last else 1):04d}"
        form = ProductionOrderForm(initial={
            'number': next_num,
            'planned_date': timezone.now().date(),
            'priority': 'normal',
        })
    return render(request, 'manufacturing/production_order_form.html', {'form': form, 'title': 'Nueva Orden de Produccion'})


@login_required
def production_order_detail(request, pk):
    order = get_object_or_404(
        ProductionOrder.objects.select_related('product', 'bom', 'warehouse', 'created_by', 'sales_order'), pk=pk
    )
    components = order.components.select_related('component', 'unit')
    return render(request, 'manufacturing/production_order_detail.html', {
        'order': order, 'components': components,
    })


@login_required
def production_order_confirm(request, pk):
    """Confirm production order - reserves component stock."""
    order = get_object_or_404(ProductionOrder, pk=pk)
    if order.status != 'draft':
        messages.warning(request, 'Solo se pueden confirmar ordenes en borrador.')
        return redirect('manufacturing:production_order_detail', pk=pk)

    # Check component availability
    from apps.logistics.models import StockLevel
    stock_issues = []
    for comp in order.components.all():
        stock = StockLevel.objects.filter(product=comp.component, warehouse=order.warehouse).first()
        available = stock.available if stock else 0
        comp.is_available = available >= comp.quantity_required
        comp.save(update_fields=['is_available'])
        if not comp.is_available:
            stock_issues.append(f"{comp.component.name}: disponible {available}, necesario {comp.quantity_required}")

    if stock_issues:
        messages.warning(request, 'Componentes con stock insuficiente: ' + '; '.join(stock_issues))

    order.status = 'confirmed'
    order.save(update_fields=['status'])
    messages.success(request, f'Orden {order.number} confirmada.')
    return redirect('manufacturing:production_order_detail', pk=pk)


@login_required
def production_order_start(request, pk):
    """Start production - consumes component stock."""
    order = get_object_or_404(ProductionOrder, pk=pk)
    if order.status != 'confirmed':
        messages.warning(request, 'La orden debe estar confirmada para iniciar.')
        return redirect('manufacturing:production_order_detail', pk=pk)

    from apps.logistics.models import StockMovement, StockLevel

    # Consume components
    for comp in order.components.all():
        StockMovement.objects.create(
            movement_type='out',
            product=comp.component,
            warehouse=order.warehouse,
            quantity=comp.quantity_required,
            reference=f"Produccion {order.number}",
            reference_type='production',
            reference_id=order.pk,
            reason=f"Consumo para produccion de {order.product.name}",
            performed_by=request.user,
        )
        stock, _ = StockLevel.objects.get_or_create(
            product=comp.component, warehouse=order.warehouse,
            defaults={'quantity': 0, 'reserved': 0}
        )
        stock.quantity -= comp.quantity_required
        stock.save(update_fields=['quantity'])
        comp.quantity_consumed = comp.quantity_required
        comp.save(update_fields=['quantity_consumed'])

    order.status = 'in_production'
    order.start_date = timezone.now()
    order.save(update_fields=['status', 'start_date'])
    messages.success(request, f'Produccion iniciada. Componentes descontados del stock.')
    return redirect('manufacturing:production_order_detail', pk=pk)


@login_required
def production_order_complete(request, pk):
    """Complete production - adds finished product to stock."""
    order = get_object_or_404(ProductionOrder, pk=pk)
    if order.status not in ('in_production', 'quality_check'):
        messages.warning(request, 'La orden debe estar en produccion.')
        return redirect('manufacturing:production_order_detail', pk=pk)

    qty_produced = request.POST.get('quantity_produced', order.quantity)
    qty_rejected = request.POST.get('quantity_rejected', 0)

    from apps.logistics.models import StockMovement, StockLevel

    qty_produced = Decimal(str(qty_produced))
    qty_rejected = Decimal(str(qty_rejected))

    # Add finished product to stock
    StockMovement.objects.create(
        movement_type='in',
        product=order.product,
        warehouse=order.warehouse,
        quantity=qty_produced,
        unit_cost=order.estimated_cost / order.quantity if order.quantity else 0,
        reference=f"Produccion {order.number}",
        reference_type='production',
        reference_id=order.pk,
        reason=f"Producto terminado - {order.product.name}",
        performed_by=request.user,
    )
    stock, _ = StockLevel.objects.get_or_create(
        product=order.product, warehouse=order.warehouse,
        defaults={'quantity': 0, 'reserved': 0}
    )
    stock.quantity += qty_produced
    stock.save(update_fields=['quantity'])

    order.quantity_produced = qty_produced
    order.quantity_rejected = qty_rejected
    order.status = 'completed'
    order.end_date = timezone.now()
    order.save(update_fields=['quantity_produced', 'quantity_rejected', 'status', 'end_date'])

    messages.success(request, f'Produccion completada. {qty_produced} unidades de {order.product.name} ingresadas al stock.')
    return redirect('manufacturing:production_order_detail', pk=pk)
