from django.contrib.auth.decorators import login_required
from django.http import HttpResponse
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.db.models import Q, Sum, Count, Min, Max
from django.utils import timezone
from decimal import Decimal
from datetime import timedelta

from .models import Invoice, InvoiceItem, PaymentRecord, AccountPayable, DocumentSeries
from .forms import InvoiceForm, PaymentRecordForm, DocumentSeriesForm
from apps.sunat_integration.services import SunatService, _flag_active


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

            # Series validation (if enabled)
            if _flag_active('invoice_series_validation'):
                valid_prefixes = {'01': 'F', '03': 'B', '07': 'F', '08': 'F'}
                expected = valid_prefixes.get(invoice.doc_type, '')
                if expected and not invoice.series.startswith(expected):
                    messages.error(request, f'Serie invalida. Para {invoice.get_doc_type_display()} debe iniciar con "{expected}" (ej: {expected}001).')
                    return render(request, 'accounting/invoice_form.html', {'form': form, 'title': 'Nuevo Comprobante'})

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

            # Auto-send to SUNAT if enabled
            if _flag_active('invoice_auto_send_sunat') and invoice.status == 'draft':
                invoice.status = 'issued'
                invoice.save(update_fields=['status'])
                try:
                    from apps.sunat_integration.tasks import send_invoice_to_sunat
                    send_invoice_to_sunat.delay(invoice.pk)
                    messages.info(request, 'Comprobante enviado a SUNAT en segundo plano.')
                except Exception:
                    pass

            return redirect('accounting:invoice_detail', pk=invoice.pk)
    else:
        # Handle doc_type from URL param (PWA shortcut support)
        initial = {'issue_date': timezone.now().date()}
        doc_type_param = request.GET.get('doc_type', '')
        if doc_type_param in ('01', '03', '07', '08'):
            initial['doc_type'] = doc_type_param
        form = InvoiceForm(initial=initial)
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
        'pdf_enabled': _flag_active('invoice_pdf_generation'),
        'void_enabled': _flag_active('sunat_comunicacion_baja'),
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
def invoice_download_pdf(request, pk):
    """Generate and download invoice PDF."""
    invoice = get_object_or_404(Invoice, pk=pk)

    if not _flag_active('invoice_pdf_generation'):
        messages.warning(request, 'Generacion de PDF no habilitada. Activar feature flag: invoice_pdf_generation')
        return redirect('accounting:invoice_detail', pk=pk)

    service = SunatService()
    pdf_content = service.generate_invoice_pdf(invoice)

    if pdf_content:
        from django.core.files.base import ContentFile
        pdf_filename = f"{invoice.full_number}.pdf"
        invoice.pdf_file.save(pdf_filename, ContentFile(pdf_content), save=True)

        response = HttpResponse(pdf_content, content_type='application/pdf')
        response['Content-Disposition'] = f'inline; filename="{pdf_filename}"'
        return response
    else:
        messages.error(request, 'Error al generar el PDF.')
        return redirect('accounting:invoice_detail', pk=pk)


@login_required
def invoice_void(request, pk):
    """Void an invoice via Comunicacion de Baja."""
    invoice = get_object_or_404(Invoice, pk=pk)

    if not _flag_active('sunat_comunicacion_baja'):
        messages.warning(request, 'Comunicacion de Baja no habilitada. Activar feature flag: sunat_comunicacion_baja')
        return redirect('accounting:invoice_detail', pk=pk)

    if request.method == 'POST':
        reason = request.POST.get('reason', 'Anulacion de comprobante')
        invoice.notes = reason
        invoice.save(update_fields=['notes'])

        service = SunatService()
        result = service.send_voided_documents(timezone.now().date(), [invoice])
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


@login_required
def petty_cash(request):
    """Caja Chica management."""
    from .models import PettyCash, PettyCashTransaction
    from .forms import PettyCashForm, PettyCashTransactionForm

    cashes = PettyCash.objects.select_related('responsible').order_by('-opened_at')

    # Handle new petty cash creation
    if request.method == 'POST' and 'create_cash' in request.POST:
        form = PettyCashForm(request.POST)
        if form.is_valid():
            cash = form.save(commit=False)
            cash.current_balance = cash.initial_amount
            cash.save()
            messages.success(request, f'Caja Chica "{cash.name}" creada.')
            return redirect('accounting:petty_cash')
    else:
        form = PettyCashForm()

    total_open = cashes.filter(status='open').aggregate(t=Sum('current_balance'))['t'] or Decimal('0')
    return render(request, 'accounting/petty_cash.html', {
        'cashes': cashes, 'form': form, 'total_open': total_open,
    })


@login_required
def petty_cash_detail(request, pk):
    """View and add transactions to a petty cash."""
    from .models import PettyCash, PettyCashTransaction
    from .forms import PettyCashTransactionForm

    cash = get_object_or_404(PettyCash, pk=pk)
    transactions = cash.transactions.select_related('recorded_by').order_by('-date', '-created_at')

    if request.method == 'POST':
        if 'close_cash' in request.POST and cash.status == 'open':
            cash.status = 'closed'
            cash.closed_at = timezone.now()
            cash.save()
            messages.success(request, 'Caja Chica cerrada.')
            return redirect('accounting:petty_cash')

        form = PettyCashTransactionForm(request.POST, request.FILES)
        if form.is_valid():
            txn = form.save(commit=False)
            txn.petty_cash = cash
            txn.recorded_by = request.user
            txn.save()
            # Update balance
            if txn.transaction_type == 'income':
                cash.current_balance += txn.amount
            else:
                cash.current_balance -= txn.amount
            cash.save(update_fields=['current_balance'])
            messages.success(request, 'Movimiento registrado.')
            return redirect('accounting:petty_cash_detail', pk=pk)
    else:
        form = PettyCashTransactionForm(initial={'date': timezone.now().date()})

    total_income = transactions.filter(transaction_type='income').aggregate(t=Sum('amount'))['t'] or Decimal('0')
    total_expense = transactions.filter(transaction_type='expense').aggregate(t=Sum('amount'))['t'] or Decimal('0')

    return render(request, 'accounting/petty_cash_detail.html', {
        'cash': cash, 'transactions': transactions, 'form': form,
        'total_income': total_income, 'total_expense': total_expense,
    })


@login_required
def accounts_receivable(request):
    """Cuentas por Cobrar."""
    from .models import AccountReceivable
    from .forms import AccountReceivableForm

    receivables = AccountReceivable.objects.select_related('customer', 'invoice').order_by('due_date')

    status_filter = request.GET.get('status', '')
    if status_filter:
        receivables = receivables.filter(status=status_filter)

    # Auto-update overdue
    today = timezone.now().date()
    AccountReceivable.objects.filter(
        status='pending', due_date__lt=today
    ).update(status='overdue')

    if request.method == 'POST':
        form = AccountReceivableForm(request.POST)
        if form.is_valid():
            ar = form.save(commit=False)
            ar.created_by = request.user
            ar.save()
            messages.success(request, 'Cuenta por cobrar registrada.')
            return redirect('accounting:accounts_receivable')
    else:
        form = AccountReceivableForm(initial={
            'issue_date': timezone.now().date(),
            'due_date': timezone.now().date() + timedelta(days=30),
        })

    total_pending = receivables.filter(status__in=['pending', 'partial', 'overdue']).aggregate(
        t=Sum('total'))['t'] or Decimal('0')
    total_collected = receivables.aggregate(t=Sum('collected_amount'))['t'] or Decimal('0')
    total_overdue = receivables.filter(status='overdue').aggregate(t=Sum('total'))['t'] or Decimal('0')

    return render(request, 'accounting/accounts_receivable.html', {
        'receivables': receivables, 'form': form,
        'total_pending': total_pending, 'total_collected': total_collected,
        'total_overdue': total_overdue,
    })


@login_required
def accounts_receivable_collect(request, pk):
    """Register a collection for an account receivable."""
    from .models import AccountReceivable

    ar = get_object_or_404(AccountReceivable, pk=pk)
    if request.method == 'POST':
        amount = Decimal(request.POST.get('amount', '0'))
        if amount > 0:
            ar.collected_amount += amount
            if ar.collected_amount >= ar.total:
                ar.status = 'collected'
            else:
                ar.status = 'partial'
            ar.save()
            messages.success(request, f'Cobro de S/ {amount} registrado.')
    return redirect('accounting:accounts_receivable')


@login_required
def daily_receipt_summary(request):
    """Resumen Diario de Boletas for SUNAT."""
    from .models import Invoice

    date_filter = request.GET.get('date', '')
    if date_filter:
        from datetime import datetime
        try:
            filter_date = datetime.strptime(date_filter, '%Y-%m-%d').date()
        except ValueError:
            filter_date = timezone.now().date()
    else:
        filter_date = timezone.now().date()

    # Get all boletas for the date
    boletas = Invoice.objects.filter(
        doc_type='03',  # Boleta
        issue_date=filter_date,
        status__in=['issued', 'accepted', 'sent']
    ).select_related('customer').order_by('series', 'correlative')

    total = boletas.aggregate(
        total_gravada=Sum('op_gravada'),
        total_exonerada=Sum('op_exonerada'),
        total_inafecta=Sum('op_inafecta'),
        total_igv=Sum('igv'),
        total_amount=Sum('total'),
        count=Count('id'),
    )

    # Group by series
    by_series = boletas.values('series').annotate(
        count=Count('id'),
        first_correlative=Min('correlative'),
        last_correlative=Max('correlative'),
        total=Sum('total'),
    ).order_by('series')

    # Handle Resumen Diario sending
    if request.method == 'POST' and 'send_resumen' in request.POST:
        if _flag_active('sunat_resumen_diario'):
            service = SunatService()
            result = service.send_daily_summary(filter_date, list(boletas))
            if result['success']:
                messages.success(request, result['message'])
            else:
                messages.error(request, result['message'])
        else:
            messages.warning(request, 'Resumen Diario no habilitado. Activar feature flag: sunat_resumen_diario')

    return render(request, 'accounting/daily_receipt_summary.html', {
        'boletas': boletas, 'filter_date': filter_date,
        'summary': total, 'by_series': by_series,
        'resumen_enabled': _flag_active('sunat_resumen_diario'),
    })


@login_required
def taxpayer_list(request):
    """Contribuyentes - List of companies/taxpayers configured."""
    from apps.core.models import Company

    companies = Company.objects.all()
    return render(request, 'accounting/taxpayer_list.html', {
        'companies': companies,
    })
