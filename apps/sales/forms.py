from django import forms
from .models import SalesQuotation, SalesQuotationItem, SalesOrder, SalesOrderItem, PickingOrder


class SalesQuotationForm(forms.ModelForm):
    class Meta:
        model = SalesQuotation
        fields = [
            'number', 'customer', 'contact_name', 'contact_email', 'contact_phone',
            'status', 'issue_date', 'valid_until', 'payment_terms', 'delivery_terms',
            'delivery_time', 'discount_percent', 'notes', 'internal_notes',
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
            'discount_amount', 'notes', 'internal_notes',
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
