from django.contrib.auth.decorators import login_required
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.db.models import Q, Sum, F
from decimal import Decimal

from .models import (
    Product, Category, Warehouse, StockLevel, StockMovement,
    PurchaseOrder, PurchaseOrderItem
)
from .forms import ProductForm, WarehouseForm, StockMovementForm, PurchaseOrderForm


@login_required
def product_list(request):
    query = request.GET.get('q', '')
    category_id = request.GET.get('category', '')
    products = Product.objects.filter(is_active=True).select_related('category', 'brand', 'unit')
    if query:
        products = products.filter(
            Q(name__icontains=query) | Q(sku__icontains=query) | Q(barcode__icontains=query)
        )
    if category_id:
        products = products.filter(category_id=category_id)

    # Annotate stock
    products = products.annotate(current_stock=Sum('stock_levels__quantity'))

    categories = Category.objects.filter(is_active=True)
    return render(request, 'logistics/product_list.html', {
        'products': products, 'categories': categories, 'query': query
    })


@login_required
def product_create(request):
    if request.method == 'POST':
        form = ProductForm(request.POST, request.FILES)
        if form.is_valid():
            form.save()
            messages.success(request, 'Producto creado exitosamente.')
            return redirect('logistics:product_list')
    else:
        form = ProductForm()
    return render(request, 'logistics/product_form.html', {'form': form, 'title': 'Nuevo Producto'})


@login_required
def product_edit(request, pk):
    product = get_object_or_404(Product, pk=pk)
    if request.method == 'POST':
        form = ProductForm(request.POST, request.FILES, instance=product)
        if form.is_valid():
            form.save()
            messages.success(request, 'Producto actualizado.')
            return redirect('logistics:product_list')
    else:
        form = ProductForm(instance=product)
    stock_levels = StockLevel.objects.filter(product=product).select_related('warehouse')
    return render(request, 'logistics/product_form.html', {
        'form': form, 'title': 'Editar Producto', 'product': product, 'stock_levels': stock_levels
    })


@login_required
def warehouse_list(request):
    warehouses = Warehouse.objects.filter(is_active=True).select_related('branch')
    return render(request, 'logistics/warehouse_list.html', {'warehouses': warehouses})


@login_required
def inventory_view(request):
    """View current inventory levels."""
    warehouse_id = request.GET.get('warehouse', '')
    query = request.GET.get('q', '')

    stock = StockLevel.objects.select_related('product', 'warehouse', 'product__category', 'product__unit')
    if warehouse_id:
        stock = stock.filter(warehouse_id=warehouse_id)
    if query:
        stock = stock.filter(
            Q(product__name__icontains=query) | Q(product__sku__icontains=query)
        )

    warehouses = Warehouse.objects.filter(is_active=True)

    # Low stock alerts
    low_stock = stock.filter(
        product__track_inventory=True,
        quantity__lte=F('product__min_stock')
    )

    return render(request, 'logistics/inventory.html', {
        'stock_levels': stock, 'warehouses': warehouses, 'low_stock': low_stock, 'query': query
    })


@login_required
def stock_movement_list(request):
    movements = StockMovement.objects.select_related(
        'product', 'warehouse', 'performed_by'
    ).order_by('-created_at')[:200]
    return render(request, 'logistics/movement_list.html', {'movements': movements})


@login_required
def stock_movement_create(request):
    if request.method == 'POST':
        form = StockMovementForm(request.POST)
        if form.is_valid():
            movement = form.save(commit=False)
            movement.performed_by = request.user
            movement.save()

            # Update stock level
            stock, _ = StockLevel.objects.get_or_create(
                product=movement.product, warehouse=movement.warehouse,
                defaults={'quantity': 0}
            )

            if movement.movement_type in ('in', 'return'):
                stock.quantity += movement.quantity
            elif movement.movement_type == 'out':
                stock.quantity -= movement.quantity
            elif movement.movement_type == 'adjustment':
                stock.quantity = movement.quantity
            elif movement.movement_type == 'transfer' and movement.destination_warehouse:
                stock.quantity -= movement.quantity
                dest_stock, _ = StockLevel.objects.get_or_create(
                    product=movement.product, warehouse=movement.destination_warehouse,
                    defaults={'quantity': 0}
                )
                dest_stock.quantity += movement.quantity
                dest_stock.save()

            stock.save()
            messages.success(request, 'Movimiento de stock registrado.')
            return redirect('logistics:movement_list')
    else:
        form = StockMovementForm()
    return render(request, 'logistics/movement_form.html', {'form': form, 'title': 'Nuevo Movimiento'})


@login_required
def purchase_order_list(request):
    orders = PurchaseOrder.objects.select_related('supplier', 'warehouse').order_by('-created_at')
    return render(request, 'logistics/purchase_order_list.html', {'orders': orders})


@login_required
def purchase_order_create(request):
    if request.method == 'POST':
        form = PurchaseOrderForm(request.POST)
        if form.is_valid():
            order = form.save(commit=False)
            order.created_by = request.user
            order.save()
            messages.success(request, 'Orden de compra creada.')
            return redirect('logistics:purchase_order_list')
    else:
        form = PurchaseOrderForm()
    return render(request, 'logistics/purchase_order_form.html', {'form': form, 'title': 'Nueva Orden de Compra'})


@login_required
def dispatch_guide_list(request):
    """Guías de Remisión list."""
    from .models import DispatchGuide

    guides = DispatchGuide.objects.select_related('recipient', 'created_by').order_by('-created_at')

    status_filter = request.GET.get('status', '')
    if status_filter:
        guides = guides.filter(status=status_filter)

    query = request.GET.get('q', '')
    if query:
        guides = guides.filter(
            Q(series__icontains=query) | Q(recipient__name__icontains=query) | Q(carrier_name__icontains=query)
        )

    return render(request, 'logistics/dispatch_guide_list.html', {'guides': guides[:100]})


@login_required
def dispatch_guide_create(request):
    """Create a new dispatch guide."""
    from .forms import DispatchGuideForm
    from django.utils import timezone

    if request.method == 'POST':
        form = DispatchGuideForm(request.POST)
        if form.is_valid():
            guide = form.save(commit=False)
            guide.created_by = request.user
            guide.save()
            messages.success(request, f'Guía de Remisión {guide.full_number} creada.')
            return redirect('logistics:dispatch_guide_list')
    else:
        form = DispatchGuideForm(initial={
            'issue_date': timezone.now().date(),
            'transfer_start_date': timezone.now().date(),
        })
    return render(request, 'logistics/dispatch_guide_form.html', {'form': form, 'title': 'Nueva Guía de Remisión'})


@login_required
def dispatch_guide_detail(request, pk):
    """View dispatch guide details."""
    from .models import DispatchGuide

    guide = get_object_or_404(DispatchGuide, pk=pk)
    items = guide.items.select_related('product', 'unit')
    return render(request, 'logistics/dispatch_guide_detail.html', {'guide': guide, 'items': items})
