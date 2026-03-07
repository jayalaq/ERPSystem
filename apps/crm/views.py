from django.contrib.auth.decorators import login_required
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.db.models import Q, Sum, Count

from .models import Customer, Supplier, Opportunity, Interaction
from .forms import CustomerForm, SupplierForm, OpportunityForm, InteractionForm


@login_required
def customer_list(request):
    query = request.GET.get('q', '')
    customers = Customer.objects.filter(is_active=True)
    if query:
        customers = customers.filter(
            Q(name__icontains=query) | Q(doc_number__icontains=query) | Q(email__icontains=query)
        )
    return render(request, 'crm/customer_list.html', {'customers': customers, 'query': query})


@login_required
def customer_create(request):
    if request.method == 'POST':
        form = CustomerForm(request.POST)
        if form.is_valid():
            customer = form.save(commit=False)
            customer.created_by = request.user
            customer.save()
            messages.success(request, 'Cliente creado exitosamente.')
            return redirect('crm:customer_detail', pk=customer.pk)
    else:
        form = CustomerForm()
    return render(request, 'crm/customer_form.html', {'form': form, 'title': 'Nuevo Cliente'})


@login_required
def customer_detail(request, pk):
    customer = get_object_or_404(Customer, pk=pk)
    interactions = customer.interactions.all()[:10]
    opportunities = customer.opportunities.all()
    return render(request, 'crm/customer_detail.html', {
        'customer': customer, 'interactions': interactions, 'opportunities': opportunities
    })


@login_required
def customer_edit(request, pk):
    customer = get_object_or_404(Customer, pk=pk)
    if request.method == 'POST':
        form = CustomerForm(request.POST, instance=customer)
        if form.is_valid():
            form.save()
            messages.success(request, 'Cliente actualizado.')
            return redirect('crm:customer_detail', pk=pk)
    else:
        form = CustomerForm(instance=customer)
    return render(request, 'crm/customer_form.html', {'form': form, 'title': 'Editar Cliente'})


@login_required
def supplier_list(request):
    query = request.GET.get('q', '')
    suppliers = Supplier.objects.filter(is_active=True)
    if query:
        suppliers = suppliers.filter(
            Q(name__icontains=query) | Q(doc_number__icontains=query)
        )
    return render(request, 'crm/supplier_list.html', {'suppliers': suppliers, 'query': query})


@login_required
def supplier_create(request):
    if request.method == 'POST':
        form = SupplierForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, 'Proveedor creado exitosamente.')
            return redirect('crm:supplier_list')
    else:
        form = SupplierForm()
    return render(request, 'crm/supplier_form.html', {'form': form, 'title': 'Nuevo Proveedor'})


@login_required
def supplier_edit(request, pk):
    supplier = get_object_or_404(Supplier, pk=pk)
    if request.method == 'POST':
        form = SupplierForm(request.POST, instance=supplier)
        if form.is_valid():
            form.save()
            messages.success(request, 'Proveedor actualizado.')
            return redirect('crm:supplier_list')
    else:
        form = SupplierForm(instance=supplier)
    return render(request, 'crm/supplier_form.html', {'form': form, 'title': 'Editar Proveedor'})


@login_required
def opportunity_list(request):
    stage = request.GET.get('stage', '')
    opportunities = Opportunity.objects.select_related('customer', 'assigned_to')
    if stage:
        opportunities = opportunities.filter(stage=stage)
    # Pipeline summary
    pipeline = Opportunity.objects.exclude(
        stage__in=['closed_won', 'closed_lost']
    ).values('stage').annotate(
        count=Count('id'), total=Sum('expected_amount')
    )
    return render(request, 'crm/opportunity_list.html', {
        'opportunities': opportunities, 'pipeline': pipeline, 'current_stage': stage
    })


@login_required
def opportunity_create(request):
    if request.method == 'POST':
        form = OpportunityForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, 'Oportunidad creada.')
            return redirect('crm:opportunity_list')
    else:
        form = OpportunityForm()
    return render(request, 'crm/opportunity_form.html', {'form': form, 'title': 'Nueva Oportunidad'})


@login_required
def opportunity_edit(request, pk):
    opportunity = get_object_or_404(Opportunity, pk=pk)
    if request.method == 'POST':
        form = OpportunityForm(request.POST, instance=opportunity)
        if form.is_valid():
            form.save()
            messages.success(request, 'Oportunidad actualizada.')
            return redirect('crm:opportunity_list')
    else:
        form = OpportunityForm(instance=opportunity)
    return render(request, 'crm/opportunity_form.html', {'form': form, 'title': 'Editar Oportunidad'})


@login_required
def interaction_create(request):
    customer_id = request.GET.get('customer')
    initial = {}
    if customer_id:
        initial['customer'] = customer_id
    if request.method == 'POST':
        form = InteractionForm(request.POST)
        if form.is_valid():
            interaction = form.save(commit=False)
            interaction.performed_by = request.user
            interaction.save()
            messages.success(request, 'Interacción registrada.')
            return redirect('crm:customer_detail', pk=interaction.customer.pk)
    else:
        form = InteractionForm(initial=initial)
    return render(request, 'crm/interaction_form.html', {'form': form, 'title': 'Nueva Interacción'})
