from django import forms
from .models import (
    SalesQuotation, SalesQuotationItem,
    SalesOrder, SalesOrderItem,
    PickingOrder,
    PriceList, PriceListItem,
    PaymentTerm, PaymentTermInstallment,
)


class SalesQuotationForm(forms.ModelForm):
    class Meta:
        model = SalesQuotation
        fields = [
            'number', 'customer', 'contact_name', 'contact_email', 'contact_phone',
            'status', 'issue_date', 'valid_until', 'payment_terms', 'payment_term',
            'price_list', 'delivery_terms', 'delivery_time', 'discount_percent',
            'notes', 'internal_notes',
        ]
        widgets = {
            'number': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'COT-0001'}),
            'customer': forms.Select(attrs={'class': 'form-select'}),
            'contact_name': forms.TextInput(attrs={'class': 'form-control'}),
            'contact_email': forms.EmailInput(attrs={'class': 'form-control'}),
            'contact_phone': forms.TextInput(attrs={'class': 'form-control'}),
            'status': forms.Select(attrs={'class': 'form-select'}),
            'issue_date': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'valid_until': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'payment_terms': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Contado'}),
            'payment_term': forms.Select(attrs={'class': 'form-select'}),
            'price_list': forms.Select(attrs={'class': 'form-select'}),
            'delivery_terms': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Puesto en almacen'}),
            'delivery_time': forms.TextInput(attrs={'class': 'form-control', 'placeholder': '3-5 dias habiles'}),
            'discount_percent': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01', 'min': '0', 'max': '100'}),
            'notes': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'internal_notes': forms.Textarea(attrs={'class': 'form-control', 'rows': 2}),
        }


class SalesQuotationItemForm(forms.ModelForm):
    class Meta:
        model = SalesQuotationItem
        fields = ['product', 'description', 'quantity', 'unit', 'unit_price', 'discount', 'affectation_type']
        widgets = {
            'product': forms.Select(attrs={'class': 'form-select product-select'}),
            'description': forms.TextInput(attrs={'class': 'form-control'}),
            'quantity': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.001', 'min': '0.001'}),
            'unit': forms.Select(attrs={'class': 'form-select'}),
            'unit_price': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
            'discount': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
            'affectation_type': forms.Select(
                choices=[('10', 'Gravado'), ('20', 'Exonerado'), ('30', 'Inafecto')],
                attrs={'class': 'form-select'}
            ),
        }


class SalesOrderForm(forms.ModelForm):
    class Meta:
        model = SalesOrder
        fields = [
            'number', 'customer', 'warehouse', 'status', 'priority',
            'order_date', 'expected_date', 'delivery_address', 'payment_terms',
            'payment_term', 'price_list', 'discount_amount', 'notes', 'internal_notes',
        ]
        widgets = {
            'number': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'PED-0001'}),
            'customer': forms.Select(attrs={'class': 'form-select'}),
            'warehouse': forms.Select(attrs={'class': 'form-select'}),
            'status': forms.Select(attrs={'class': 'form-select'}),
            'priority': forms.Select(attrs={'class': 'form-select'}),
            'order_date': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'expected_date': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'delivery_address': forms.Textarea(attrs={'class': 'form-control', 'rows': 2}),
            'payment_terms': forms.TextInput(attrs={'class': 'form-control'}),
            'payment_term': forms.Select(attrs={'class': 'form-select'}),
            'price_list': forms.Select(attrs={'class': 'form-select'}),
            'discount_amount': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
            'notes': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'internal_notes': forms.Textarea(attrs={'class': 'form-control', 'rows': 2}),
        }


class SalesOrderItemForm(forms.ModelForm):
    class Meta:
        model = SalesOrderItem
        fields = ['product', 'description', 'quantity', 'unit', 'unit_price', 'discount', 'affectation_type']
        widgets = {
            'product': forms.Select(attrs={'class': 'form-select product-select'}),
            'description': forms.TextInput(attrs={'class': 'form-control'}),
            'quantity': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.001', 'min': '0.001'}),
            'unit': forms.Select(attrs={'class': 'form-select'}),
            'unit_price': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
            'discount': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
            'affectation_type': forms.Select(
                choices=[('10', 'Gravado'), ('20', 'Exonerado'), ('30', 'Inafecto')],
                attrs={'class': 'form-select'}
            ),
        }


class PickingOrderForm(forms.ModelForm):
    class Meta:
        model = PickingOrder
        fields = ['assigned_to', 'scheduled_date', 'notes']
        widgets = {
            'assigned_to': forms.Select(attrs={'class': 'form-select'}),
            'scheduled_date': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'notes': forms.Textarea(attrs={'class': 'form-control', 'rows': 2}),
        }


class PriceListForm(forms.ModelForm):
    class Meta:
        model = PriceList
        fields = ['name', 'code', 'currency', 'is_active', 'is_default', 'valid_from', 'valid_until', 'notes']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Lista precio general'}),
            'code': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'LP-001'}),
            'currency': forms.Select(attrs={'class': 'form-select'}),
            'is_active': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'is_default': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'valid_from': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'valid_until': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'notes': forms.Textarea(attrs={'class': 'form-control', 'rows': 2}),
        }


class PriceListItemForm(forms.ModelForm):
    class Meta:
        model = PriceListItem
        fields = ['product', 'price', 'min_quantity']
        widgets = {
            'product': forms.Select(attrs={'class': 'form-select'}),
            'price': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
            'min_quantity': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.001', 'value': '1'}),
        }


class PaymentTermForm(forms.ModelForm):
    class Meta:
        model = PaymentTerm
        fields = ['name', 'code', 'is_active', 'is_immediate', 'notes']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': '30/70 a 30 dias'}),
            'code': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'PT-001'}),
            'is_active': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'is_immediate': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'notes': forms.Textarea(attrs={'class': 'form-control', 'rows': 2}),
        }


class PaymentTermInstallmentForm(forms.ModelForm):
    class Meta:
        model = PaymentTermInstallment
        fields = ['sequence', 'percentage', 'days']
        widgets = {
            'sequence': forms.NumberInput(attrs={'class': 'form-control', 'min': '1'}),
            'percentage': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01', 'min': '0', 'max': '100'}),
            'days': forms.NumberInput(attrs={'class': 'form-control', 'min': '0'}),
        }
