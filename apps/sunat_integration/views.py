from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.shortcuts import render
from django.views.decorators.http import require_POST

from apps.accounting.models import Invoice
from .models import SunatLog
from .services import SunatService


@login_required
def consult_ruc(request):
    """AJAX endpoint to consult RUC from SUNAT."""
    ruc = request.GET.get('ruc', '')
    if not ruc or len(ruc) != 11:
        return JsonResponse({'success': False, 'message': 'RUC inválido'})

    service = SunatService()
    result = service.consult_ruc(ruc)
    return JsonResponse(result)


@login_required
@require_POST
def send_invoice(request, invoice_id):
    """Send an invoice to SUNAT."""
    try:
        invoice = Invoice.objects.get(id=invoice_id)
    except Invoice.DoesNotExist:
        return JsonResponse({'success': False, 'message': 'Comprobante no encontrado'})

    service = SunatService()
    result = service.send_invoice(invoice)
    return JsonResponse(result)


@login_required
def exchange_rate(request):
    """Get current exchange rate."""
    service = SunatService()
    result = service.get_exchange_rate()
    return JsonResponse(result)


@login_required
def sunat_logs(request):
    """View SUNAT interaction logs."""
    logs = SunatLog.objects.all()[:100]
    return render(request, 'accounting/sunat_logs.html', {'logs': logs})
