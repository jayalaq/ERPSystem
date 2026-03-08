from django.shortcuts import render, redirect
from django.contrib import messages
from django.http import JsonResponse
from django.views.decorators.http import require_POST

from .forms import ContactForm
from .models import ContactMessage
from apps.crm.models import Customer, Opportunity


def landing_page(request):
    """Public landing page."""
    form = ContactForm()
    return render(request, 'website/landing.html', {'form': form})


@require_POST
def contact_submit(request):
    """Handle contact form submission and create CRM lead."""
    form = ContactForm(request.POST)
    if form.is_valid():
        contact = form.save(commit=False)
        contact.ip_address = _get_client_ip(request)
        contact.save()

        # Auto-create CRM customer + opportunity
        _create_crm_lead(contact)

        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse({'success': True, 'message': 'Mensaje enviado correctamente.'})

        messages.success(request, 'Tu mensaje ha sido enviado. Nos pondremos en contacto contigo pronto.')
        return redirect('website:landing')

    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return JsonResponse({'success': False, 'errors': form.errors}, status=400)

    return render(request, 'website/landing.html', {'form': form})


def _get_client_ip(request):
    x_forwarded = request.META.get('HTTP_X_FORWARDED_FOR')
    if x_forwarded:
        return x_forwarded.split(',')[0].strip()
    return request.META.get('REMOTE_ADDR')


def _create_crm_lead(contact):
    """Create a Customer and Opportunity from a contact form submission."""
    try:
        # Find or create customer
        doc_number = contact.ruc if contact.ruc else contact.email
        doc_type = 'RUC' if contact.ruc else 'DNI'

        customer, created = Customer.objects.get_or_create(
            doc_number=doc_number,
            defaults={
                'customer_type': 'business' if contact.ruc else 'individual',
                'doc_type': doc_type,
                'name': contact.company or contact.name,
                'email': contact.email,
                'phone': contact.phone,
                'notes': f'Lead desde landing page: {contact.message}',
            }
        )

        # Map service interest to opportunity title
        service_labels = dict(ContactMessage.ServiceInterest.choices)
        service_name = service_labels.get(contact.service_interest, 'Consultoría')

        opportunity = Opportunity.objects.create(
            customer=customer,
            title=f"[Web] {service_name} - {contact.name}",
            description=contact.message,
            stage='prospecting',
            priority='medium',
            source='landing_page',
        )

        contact.status = 'converted'
        contact.opportunity = opportunity
        contact.save()
    except Exception:
        # Don't fail the contact form if CRM creation fails
        pass
