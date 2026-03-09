from django.contrib.auth.decorators import login_required
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.db.models import Q, Sum, Count
from django.utils import timezone
from django.http import HttpResponse, JsonResponse
from decimal import Decimal
import io

from .models import (
    SalesQuotation, SalesQuotationItem,
    SalesOrder, SalesOrderItem,
    PickingOrder, PickingOrderItem,
    PriceList, PriceListItem,
    PaymentTerm, PaymentTermInstallment,
    SalesActivityLog,
)
from .forms import (
    SalesQuotationForm, SalesQuotationItemForm,
    SalesOrderForm, SalesOrderItemForm,
    PickingOrderForm,
    PriceListForm, PriceListItemForm,
    PaymentTermForm, PaymentTermInstallmentForm,
)


def log_activity(user, title, activity_type='note', description='',
                 old_value='', new_value='', quotation=None, order=None):
    """Helper to create activity log entries."""
    SalesActivityLog.objects.create(
        quotation=quotation,
        order=order,
        activity_type=activity_type,
        title=title,
        description=description,
        old_value=old_value,
        new_value=new_value,
        user=user,
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
            log_activity(
                request.user, f'Cotizacion {quotation.number} creada',
                activity_type='status_change', new_value='draft', quotation=quotation,
            )
            messages.success(request, f'Cotizacion {quotation.number} creada.')
            return redirect('sales:quotation_detail', pk=quotation.pk)
    else:
        # Auto-generate number
        last = SalesQuotation.objects.order_by('-id').first()
        next_num = f"COT-{(last.id + 1 if last else 1):04d}"
        default_price_list = PriceList.objects.filter(is_active=True, is_default=True).first()
        form = SalesQuotationForm(initial={
            'number': next_num,
            'issue_date': timezone.now().date(),
            'valid_until': timezone.now().date() + timezone.timedelta(days=15),
            'status': 'draft',
            'price_list': default_price_list,
        })
    return render(request, 'sales/quotation_form.html', {'form': form, 'title': 'Nueva Cotizacion'})


@login_required
def quotation_edit(request, pk):
    quotation = get_object_or_404(SalesQuotation, pk=pk)
    old_status = quotation.status
    if request.method == 'POST':
        form = SalesQuotationForm(request.POST, instance=quotation)
        if form.is_valid():
            quotation = form.save()
            if quotation.status != old_status:
                log_activity(
                    request.user,
                    f'Estado cambiado de {dict(SalesQuotation.Status.choices).get(old_status)} a {quotation.get_status_display()}',
                    activity_type='status_change',
                    old_value=old_status, new_value=quotation.status,
                    quotation=quotation,
                )
            messages.success(request, 'Cotizacion actualizada.')
            return redirect('sales:quotation_detail', pk=quotation.pk)
    else:
        form = SalesQuotationForm(instance=quotation)
    return render(request, 'sales/quotation_form.html', {
        'form': form, 'title': f'Editar {quotation.number}', 'quotation': quotation,
    })


@login_required
def quotation_detail(request, pk):
    quotation = get_object_or_404(
        SalesQuotation.objects.select_related('customer', 'created_by', 'price_list', 'payment_term'), pk=pk
    )
    items = quotation.items.select_related('product', 'unit')
    item_form = SalesQuotationItemForm()
    activities = quotation.activity_logs.select_related('user').order_by('-created_at')[:50]
    return render(request, 'sales/quotation_detail.html', {
        'quotation': quotation, 'items': items, 'item_form': item_form,
        'activities': activities,
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
            # Apply price list if available
            if quotation.price_list:
                pl_price = quotation.price_list.get_price(item.product)
                if pl_price and not request.POST.get('unit_price'):
                    item.unit_price = pl_price
            item.calculate_totals()
            item.save()
            quotation.recalculate_totals()
            log_activity(
                request.user,
                f'Item agregado: {item.product.name} x {item.quantity}',
                quotation=quotation,
            )
            messages.success(request, 'Item agregado.')
    return redirect('sales:quotation_detail', pk=pk)


@login_required
def quotation_remove_item(request, pk, item_pk):
    quotation = get_object_or_404(SalesQuotation, pk=pk)
    item = get_object_or_404(SalesQuotationItem, pk=item_pk, quotation=quotation)
    product_name = item.product.name
    item.delete()
    quotation.recalculate_totals()
    log_activity(request.user, f'Item eliminado: {product_name}', quotation=quotation)
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
        payment_term=quotation.payment_term,
        price_list=quotation.price_list,
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
    old_status = quotation.status
    quotation.sales_order = order
    quotation.status = 'accepted'
    quotation.save(update_fields=['sales_order', 'status'])

    log_activity(
        request.user, 'Cotizacion confirmada - Pedido creado',
        activity_type='status_change', old_value=old_status, new_value='accepted',
        quotation=quotation,
    )
    log_activity(
        request.user, f'Pedido {order.number} creado desde cotizacion {quotation.number}',
        activity_type='status_change', new_value='draft', order=order,
    )

    messages.success(request, f'Pedido {order.number} creado desde cotizacion {quotation.number}.')
    return redirect('sales:order_detail', pk=order.pk)


@login_required
def quotation_sign(request, pk):
    """Save client signature on a quotation."""
    quotation = get_object_or_404(SalesQuotation, pk=pk)
    if request.method == 'POST':
        signature_data = request.POST.get('signature', '')
        signed_by = request.POST.get('signed_by', '')
        if signature_data:
            quotation.signature = signature_data
            quotation.signed_by = signed_by
            quotation.signed_at = timezone.now()
            quotation.save(update_fields=['signature', 'signed_by', 'signed_at'])
            log_activity(
                request.user,
                f'Cotizacion firmada por {signed_by or "cliente"}',
                activity_type='signature', quotation=quotation,
            )
            messages.success(request, 'Firma guardada.')
        else:
            messages.error(request, 'No se recibio la firma.')
    return redirect('sales:quotation_detail', pk=pk)


@login_required
def quotation_add_note(request, pk):
    """Add a note to quotation activity log."""
    quotation = get_object_or_404(SalesQuotation, pk=pk)
    if request.method == 'POST':
        note = request.POST.get('note', '').strip()
        if note:
            log_activity(request.user, note, quotation=quotation)
            messages.success(request, 'Nota agregada.')
    return redirect('sales:quotation_detail', pk=pk)


@login_required
def quotation_pdf(request, pk):
    """Generate PDF for a quotation."""
    quotation = get_object_or_404(
        SalesQuotation.objects.select_related('customer', 'created_by', 'price_list', 'payment_term'), pk=pk
    )
    items = quotation.items.select_related('product', 'unit')

    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.units import mm, cm
    from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, Image
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.enums import TA_CENTER, TA_RIGHT, TA_LEFT
    from django.conf import settings as django_settings
    import base64

    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4, topMargin=1.5*cm, bottomMargin=1.5*cm,
                            leftMargin=2*cm, rightMargin=2*cm)

    styles = getSampleStyleSheet()
    styles.add(ParagraphStyle(name='DocTitle', fontSize=16, spaceAfter=6, textColor=colors.HexColor('#1a1a2e'),
                              fontName='Helvetica-Bold'))
    styles.add(ParagraphStyle(name='DocSubtitle', fontSize=10, spaceAfter=12, textColor=colors.HexColor('#666666')))
    styles.add(ParagraphStyle(name='SectionTitle', fontSize=11, spaceBefore=12, spaceAfter=6,
                              fontName='Helvetica-Bold', textColor=colors.HexColor('#1a1a2e')))
    styles.add(ParagraphStyle(name='Small', fontSize=8, textColor=colors.HexColor('#888888')))
    styles.add(ParagraphStyle(name='RightAlign', fontSize=9, alignment=TA_RIGHT))
    styles.add(ParagraphStyle(name='CellStyle', fontSize=8, leading=10))

    elements = []

    # Header
    company = django_settings.COMPANY_CONFIG
    elements.append(Paragraph(company.get('NAME', 'Mi Empresa'), styles['DocTitle']))
    elements.append(Paragraph(
        f"RUC: {company.get('RUC', '')} | {company.get('ADDRESS', '')} | {company.get('PHONE', '')}",
        styles['DocSubtitle']
    ))
    elements.append(Spacer(1, 6*mm))

    # Quotation header
    elements.append(Paragraph(f"COTIZACION {quotation.number}", styles['DocTitle']))
    elements.append(Spacer(1, 3*mm))

    # Info table
    info_data = [
        ['Cliente:', quotation.customer.name, 'Fecha:', quotation.issue_date.strftime('%d/%m/%Y')],
        ['RUC/DNI:', quotation.customer.document_number or '-', 'Valida hasta:', quotation.valid_until.strftime('%d/%m/%Y')],
        ['Contacto:', quotation.contact_name or '-', 'Estado:', quotation.get_status_display()],
    ]
    if quotation.payment_term:
        info_data.append(['Terminos de Pago:', quotation.payment_term.name, '', ''])
    elif quotation.payment_terms:
        info_data.append(['Terminos de Pago:', quotation.payment_terms, '', ''])
    if quotation.price_list:
        info_data.append(['Lista de Precios:', str(quotation.price_list), '', ''])

    info_table = Table(info_data, colWidths=[3*cm, 6*cm, 3*cm, 4.5*cm])
    info_table.setStyle(TableStyle([
        ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
        ('FONTNAME', (2, 0), (2, -1), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 9),
        ('TEXTCOLOR', (0, 0), (0, -1), colors.HexColor('#555555')),
        ('TEXTCOLOR', (2, 0), (2, -1), colors.HexColor('#555555')),
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
    ]))
    elements.append(info_table)
    elements.append(Spacer(1, 8*mm))

    # Items table
    elements.append(Paragraph("DETALLE", styles['SectionTitle']))
    table_data = [['#', 'Producto', 'Descripcion', 'Cant.', 'P. Unit.', 'Desc.', 'Subtotal', 'IGV', 'Total']]

    for i, item in enumerate(items, 1):
        table_data.append([
            str(i),
            Paragraph(item.product.sku or item.product.name[:20], styles['CellStyle']),
            Paragraph(item.description[:40], styles['CellStyle']),
            f"{item.quantity:,.0f}",
            f"S/ {item.unit_price:,.2f}",
            f"S/ {item.discount:,.2f}" if item.discount else '-',
            f"S/ {item.subtotal:,.2f}",
            f"S/ {item.igv:,.2f}",
            f"S/ {item.total:,.2f}",
        ])

    col_widths = [0.6*cm, 2.5*cm, 4*cm, 1.3*cm, 2*cm, 1.5*cm, 2*cm, 1.5*cm, 2*cm]
    items_table = Table(table_data, colWidths=col_widths, repeatRows=1)
    items_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#1a1a2e')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 8),
        ('FONTSIZE', (0, 1), (-1, -1), 8),
        ('ALIGN', (0, 0), (0, -1), 'CENTER'),
        ('ALIGN', (3, 0), (-1, -1), 'RIGHT'),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#dddddd')),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#f8f9fa')]),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('TOPPADDING', (0, 0), (-1, -1), 4),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
    ]))
    elements.append(items_table)
    elements.append(Spacer(1, 6*mm))

    # Totals
    totals_data = [
        ['', '', 'Subtotal:', f"S/ {quotation.subtotal:,.2f}"],
    ]
    if quotation.discount_amount:
        discount_label = f"Descuento ({quotation.discount_percent}%):" if quotation.discount_percent else "Descuento:"
        totals_data.append(['', '', discount_label, f"- S/ {quotation.discount_amount:,.2f}"])
    totals_data.append(['', '', 'IGV (18%):', f"S/ {quotation.igv:,.2f}"])
    totals_data.append(['', '', 'TOTAL:', f"S/ {quotation.total:,.2f}"])

    totals_table = Table(totals_data, colWidths=[6*cm, 4*cm, 3.5*cm, 3*cm])
    totals_table.setStyle(TableStyle([
        ('ALIGN', (2, 0), (-1, -1), 'RIGHT'),
        ('FONTNAME', (2, -1), (-1, -1), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 9),
        ('FONTSIZE', (2, -1), (-1, -1), 11),
        ('TEXTCOLOR', (2, 0), (2, -1), colors.HexColor('#555555')),
        ('LINEABOVE', (2, -1), (-1, -1), 1, colors.HexColor('#1a1a2e')),
        ('TOPPADDING', (0, 0), (-1, -1), 3),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 3),
    ]))
    elements.append(totals_table)

    # Payment term details
    if quotation.payment_term and quotation.payment_term.installments.exists():
        elements.append(Spacer(1, 6*mm))
        elements.append(Paragraph("CONDICIONES DE PAGO", styles['SectionTitle']))
        pt_data = [['Cuota', 'Porcentaje', 'Dias', 'Monto']]
        for inst in quotation.payment_term.installments.all():
            amount = quotation.total * inst.percentage / Decimal('100')
            pt_data.append([
                f"Cuota {inst.sequence}",
                f"{inst.percentage}%",
                f"{inst.days} dias",
                f"S/ {amount:,.2f}",
            ])
        pt_table = Table(pt_data, colWidths=[3*cm, 3*cm, 3*cm, 3*cm])
        pt_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#e8e8e8')),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, -1), 8),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#dddddd')),
            ('ALIGN', (1, 0), (-1, -1), 'CENTER'),
            ('TOPPADDING', (0, 0), (-1, -1), 3),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 3),
        ]))
        elements.append(pt_table)

    # Notes
    if quotation.notes:
        elements.append(Spacer(1, 6*mm))
        elements.append(Paragraph("NOTAS", styles['SectionTitle']))
        elements.append(Paragraph(quotation.notes, styles['Normal']))

    # Signature
    if quotation.signature:
        elements.append(Spacer(1, 10*mm))
        elements.append(Paragraph("FIRMA DEL CLIENTE", styles['SectionTitle']))
        try:
            sig_data = quotation.signature
            if ',' in sig_data:
                sig_data = sig_data.split(',')[1]
            sig_bytes = base64.b64decode(sig_data)
            sig_buffer = io.BytesIO(sig_bytes)
            sig_img = Image(sig_buffer, width=6*cm, height=3*cm)
            elements.append(sig_img)
        except Exception:
            pass
        if quotation.signed_by:
            elements.append(Paragraph(f"Firmado por: {quotation.signed_by}", styles['Small']))
        if quotation.signed_at:
            elements.append(Paragraph(f"Fecha: {quotation.signed_at:%d/%m/%Y %H:%M}", styles['Small']))

    # Footer
    elements.append(Spacer(1, 10*mm))
    elements.append(Paragraph(
        f"Documento generado el {timezone.now():%d/%m/%Y %H:%M} por {request.user.get_full_name() or request.user.username}",
        styles['Small']
    ))

    doc.build(elements)
    buffer.seek(0)

    response = HttpResponse(buffer, content_type='application/pdf')
    response['Content-Disposition'] = f'inline; filename="{quotation.number}.pdf"'
    return response


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
            log_activity(
                request.user, f'Pedido {order.number} creado',
                activity_type='status_change', new_value='draft', order=order,
            )
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
    old_status = order.status
    if request.method == 'POST':
        form = SalesOrderForm(request.POST, instance=order)
        if form.is_valid():
            order = form.save()
            if order.status != old_status:
                log_activity(
                    request.user,
                    f'Estado cambiado de {dict(SalesOrder.Status.choices).get(old_status)} a {order.get_status_display()}',
                    activity_type='status_change',
                    old_value=old_status, new_value=order.status, order=order,
                )
            messages.success(request, 'Pedido actualizado.')
            return redirect('sales:order_detail', pk=order.pk)
    else:
        form = SalesOrderForm(instance=order)
    return render(request, 'sales/order_form.html', {
        'form': form, 'title': f'Editar {order.number}', 'order': order,
    })


@login_required
def order_detail(request, pk):
    order = get_object_or_404(
        SalesOrder.objects.select_related('customer', 'warehouse', 'created_by', 'price_list', 'payment_term'), pk=pk
    )
    items = order.items.select_related('product', 'unit')
    picking_orders = order.picking_orders.select_related('assigned_to', 'warehouse')
    item_form = SalesOrderItemForm()
    activities = order.activity_logs.select_related('user').order_by('-created_at')[:50]
    return render(request, 'sales/order_detail.html', {
        'order': order, 'items': items, 'picking_orders': picking_orders,
        'item_form': item_form, 'activities': activities,
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
            # Apply price list if available
            if order.price_list:
                pl_price = order.price_list.get_price(item.product)
                if pl_price and not request.POST.get('unit_price'):
                    item.unit_price = pl_price
            item.calculate_totals()
            item.save()
            order.recalculate_totals()
            log_activity(
                request.user,
                f'Item agregado: {item.product.name} x {item.quantity}',
                order=order,
            )
            messages.success(request, 'Item agregado.')
    return redirect('sales:order_detail', pk=pk)


@login_required
def order_remove_item(request, pk, item_pk):
    order = get_object_or_404(SalesOrder, pk=pk)
    item = get_object_or_404(SalesOrderItem, pk=item_pk, order=order)
    product_name = item.product.name
    item.delete()
    order.recalculate_totals()
    log_activity(request.user, f'Item eliminado: {product_name}', order=order)
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
    log_activity(
        request.user, 'Pedido confirmado - Stock reservado',
        activity_type='status_change', old_value='draft', new_value='confirmed', order=order,
    )
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

    old_status = order.status
    order.status = 'in_process'
    order.save(update_fields=['status'])
    log_activity(
        request.user, f'Picking {picking.number} generado',
        activity_type='status_change', old_value=old_status, new_value='in_process', order=order,
    )

    messages.success(request, f'Orden de picking {picking.number} generada.')
    return redirect('sales:picking_detail', pk=picking.pk)


@login_required
def order_add_note(request, pk):
    """Add a note to order activity log."""
    order = get_object_or_404(SalesOrder, pk=pk)
    if request.method == 'POST':
        note = request.POST.get('note', '').strip()
        if note:
            log_activity(request.user, note, order=order)
            messages.success(request, 'Nota agregada.')
    return redirect('sales:order_detail', pk=pk)


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
            log_activity(
                request.user, f'Picking {picking.number} completado - Pedido listo para despacho',
                activity_type='status_change', old_value='in_process', new_value='ready', order=order,
            )

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


# ============================================
# PRICE LISTS
# ============================================
@login_required
def price_list_list(request):
    price_lists = PriceList.objects.annotate(item_count=Count('items')).order_by('name')
    return render(request, 'sales/price_list_list.html', {'price_lists': price_lists})


@login_required
def price_list_create(request):
    if request.method == 'POST':
        form = PriceListForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, 'Lista de precios creada.')
            return redirect('sales:price_list_list')
    else:
        form = PriceListForm()
    return render(request, 'sales/price_list_form.html', {'form': form, 'title': 'Nueva Lista de Precios'})


@login_required
def price_list_detail(request, pk):
    price_list = get_object_or_404(PriceList, pk=pk)
    items = price_list.items.select_related('product').order_by('product__name')
    item_form = PriceListItemForm()
    return render(request, 'sales/price_list_detail.html', {
        'price_list': price_list, 'items': items, 'item_form': item_form,
    })


@login_required
def price_list_edit(request, pk):
    price_list = get_object_or_404(PriceList, pk=pk)
    if request.method == 'POST':
        form = PriceListForm(request.POST, instance=price_list)
        if form.is_valid():
            form.save()
            messages.success(request, 'Lista de precios actualizada.')
            return redirect('sales:price_list_detail', pk=pk)
    else:
        form = PriceListForm(instance=price_list)
    return render(request, 'sales/price_list_form.html', {
        'form': form, 'title': f'Editar {price_list.name}', 'price_list': price_list,
    })


@login_required
def price_list_add_item(request, pk):
    price_list = get_object_or_404(PriceList, pk=pk)
    if request.method == 'POST':
        form = PriceListItemForm(request.POST)
        if form.is_valid():
            item = form.save(commit=False)
            item.price_list = price_list
            item.save()
            messages.success(request, 'Producto agregado a la lista.')
    return redirect('sales:price_list_detail', pk=pk)


@login_required
def price_list_remove_item(request, pk, item_pk):
    price_list = get_object_or_404(PriceList, pk=pk)
    item = get_object_or_404(PriceListItem, pk=item_pk, price_list=price_list)
    item.delete()
    messages.success(request, 'Producto eliminado de la lista.')
    return redirect('sales:price_list_detail', pk=pk)


# ============================================
# PAYMENT TERMS
# ============================================
@login_required
def payment_term_list(request):
    terms = PaymentTerm.objects.annotate(installment_count=Count('installments')).order_by('name')
    return render(request, 'sales/payment_term_list.html', {'terms': terms})


@login_required
def payment_term_create(request):
    if request.method == 'POST':
        form = PaymentTermForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, 'Termino de pago creado.')
            return redirect('sales:payment_term_list')
    else:
        form = PaymentTermForm()
    return render(request, 'sales/payment_term_form.html', {'form': form, 'title': 'Nuevo Termino de Pago'})


@login_required
def payment_term_detail(request, pk):
    term = get_object_or_404(PaymentTerm, pk=pk)
    installments = term.installments.order_by('sequence')
    inst_form = PaymentTermInstallmentForm()
    return render(request, 'sales/payment_term_detail.html', {
        'term': term, 'installments': installments, 'inst_form': inst_form,
    })


@login_required
def payment_term_edit(request, pk):
    term = get_object_or_404(PaymentTerm, pk=pk)
    if request.method == 'POST':
        form = PaymentTermForm(request.POST, instance=term)
        if form.is_valid():
            form.save()
            messages.success(request, 'Termino de pago actualizado.')
            return redirect('sales:payment_term_detail', pk=pk)
    else:
        form = PaymentTermForm(instance=term)
    return render(request, 'sales/payment_term_form.html', {
        'form': form, 'title': f'Editar {term.name}', 'term': term,
    })


@login_required
def payment_term_add_installment(request, pk):
    term = get_object_or_404(PaymentTerm, pk=pk)
    if request.method == 'POST':
        form = PaymentTermInstallmentForm(request.POST)
        if form.is_valid():
            inst = form.save(commit=False)
            inst.payment_term = term
            if not inst.sequence:
                last = term.installments.order_by('-sequence').first()
                inst.sequence = (last.sequence + 1) if last else 1
            inst.save()
            messages.success(request, 'Cuota agregada.')
    return redirect('sales:payment_term_detail', pk=pk)


@login_required
def payment_term_remove_installment(request, pk, inst_pk):
    term = get_object_or_404(PaymentTerm, pk=pk)
    inst = get_object_or_404(PaymentTermInstallment, pk=inst_pk, payment_term=term)
    inst.delete()
    messages.success(request, 'Cuota eliminada.')
    return redirect('sales:payment_term_detail', pk=pk)


# ============================================
# API: Get product price from price list
# ============================================
@login_required
def api_get_product_price(request):
    """AJAX endpoint to get product price from a price list."""
    product_id = request.GET.get('product_id')
    price_list_id = request.GET.get('price_list_id')
    if not product_id:
        return JsonResponse({'price': None})

    from apps.logistics.models import Product
    try:
        product = Product.objects.get(pk=product_id)
    except Product.DoesNotExist:
        return JsonResponse({'price': None})

    price = float(product.sale_price or 0)
    if price_list_id:
        try:
            pl = PriceList.objects.get(pk=price_list_id)
            pl_price = pl.get_price(product)
            if pl_price:
                price = float(pl_price)
        except PriceList.DoesNotExist:
            pass

    return JsonResponse({'price': price, 'name': product.name, 'sku': product.sku or ''})
