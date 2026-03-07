from django.contrib.auth.decorators import login_required
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.db.models import Q, Sum
from django.utils import timezone
from decimal import Decimal

from .models import Invoice, InvoiceItem, PaymentRecord, AccountPayable, DocumentSeries
from .forms import InvoiceForm, PaymentRecordForm, DocumentSeriesForm
from apps.sunat_integration.services import SunatService


@login_required
def invoice_list(request):
    doc_type = request.GET.get('type', '')
    status = request.GET.get('status', '')
    query = request.GET.get('q', '')

    invoices = Invoice.objects.select_related('customer').order_by('-created_at')
    if doc_type:
        invoices = invoices.filter(doc_type=doc_type)
    if status:
        invoices = invoices.filter(status=status)
    if query:
        invoices = invoices.filter(
            Q(customer__name__icontains=query) | Q(series__icontains=query)
        )

    # Summary
    total_issued = invoices.filter(status__in=['issued', 'accepted']).aggregate(
        total=Sum('total'))['total'] or Decimal('0')
    total_pending = invoices.filter(status='draft').aggregate(
        total=Sum('total'))['total'] or Decimal('0')

    return render(request, 'accounting/invoice_list.html', {
        'invoices': invoices[:100],
        'total_issued': total_issued,
        'total_pending': total_pending,
        'current_type': doc_type,
        'current_status': status,
    })


@login_required
def invoice_create(request):
    if request.method == 'POST':
        form = InvoiceForm(request.POST)
        if form.is_valid():
            invoice = form.save(commit=False)
            invoice.created_by = request.user

            # Get next correlative
            doc_series = DocumentSeries.objects.filter(
                doc_type=invoice.doc_type, series=invoice.series, is_active=True
            ).first()
            if doc_series:
                invoice.correlative = doc_series.get_next_number()
            else:
                invoice.correlative = 1

            invoice.save()
            messages.success(request, f'Comprobante {invoice.full_number} creado.')
            return redirect('accounting:invoice_detail', pk=invoice.pk)
    else:
        form = InvoiceForm(initial={'issue_date': timezone.now().date()})
    return render(request, 'accounting/invoice_form.html', {'form': form, 'title': 'Nuevo Comprobante'})


@login_required
def invoice_detail(request, pk):
    invoice = get_object_or_404(Invoice, pk=pk)
    items = invoice.items.select_related('product', 'unit')
    payments = invoice.payments.all()
    total_paid = payments.aggregate(t=Sum('amount'))['t'] or Decimal('0')
    balance = invoice.total - total_paid

    return render(request, 'accounting/invoice_detail.html', {
        'invoice': invoice, 'items': items, 'payments': payments,
        'total_paid': total_paid, 'balance': balance,
    })


@login_required
def invoice_send_sunat(request, pk):
    invoice = get_object_or_404(Invoice, pk=pk)
    service = SunatService()
    result = service.send_invoice(invoice)
    if result['success']:
        messages.success(request, result['message'])
    else:
        messages.error(request, result['message'])
    return redirect('accounting:invoice_detail', pk=pk)


@login_required
def payment_create(request):
    invoice_id = request.GET.get('invoice')
    initial = {}
    if invoice_id:
        initial['invoice'] = invoice_id
        initial['payment_date'] = timezone.now().date()

    if request.method == 'POST':
        form = PaymentRecordForm(request.POST)
        if form.is_valid():
            payment = form.save(commit=False)
            payment.recorded_by = request.user
            payment.save()
            messages.success(request, 'Pago registrado exitosamente.')
            return redirect('accounting:invoice_detail', pk=payment.invoice.pk)
    else:
        form = PaymentRecordForm(initial=initial)
    return render(request, 'accounting/payment_form.html', {'form': form, 'title': 'Registrar Pago'})


@login_required
def accounts_payable(request):
    payables = AccountPayable.objects.select_related('supplier').order_by('due_date')
    total_pending = payables.filter(status__in=['pending', 'partial', 'overdue']).aggregate(
        total=Sum('total'))['total'] or Decimal('0')
    total_paid_amount = payables.aggregate(t=Sum('paid_amount'))['t'] or Decimal('0')

    return render(request, 'accounting/accounts_payable.html', {
        'payables': payables, 'total_pending': total_pending, 'total_paid': total_paid_amount,
    })


@login_required
def document_series_list(request):
    series = DocumentSeries.objects.select_related('branch').order_by('doc_type', 'series')
    return render(request, 'accounting/document_series.html', {'series': series})


@login_required
def document_series_create(request):
    if request.method == 'POST':
        form = DocumentSeriesForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, 'Serie creada.')
            return redirect('accounting:document_series')
    else:
        form = DocumentSeriesForm()
    return render(request, 'accounting/document_series_form.html', {'form': form, 'title': 'Nueva Serie'})


@login_required
def reports_dashboard(request):
    """Financial reports dashboard."""
    today = timezone.now().date()
    month_start = today.replace(day=1)

    # Monthly invoicing
    monthly_invoices = Invoice.objects.filter(
        issue_date__gte=month_start, status__in=['issued', 'accepted']
    )
    monthly_total = monthly_invoices.aggregate(t=Sum('total'))['t'] or Decimal('0')
    monthly_igv = monthly_invoices.aggregate(t=Sum('igv'))['t'] or Decimal('0')

    # Accounts receivable
    from apps.pos.models import POSSale
    monthly_pos_sales = POSSale.objects.filter(
        created_at__date__gte=month_start, status='completed'
    ).aggregate(t=Sum('total'))['t'] or Decimal('0')

    return render(request, 'accounting/reports.html', {
        'monthly_total': monthly_total,
        'monthly_igv': monthly_igv,
        'monthly_pos_sales': monthly_pos_sales,
    })
