from django import forms
from .models import BillOfMaterials, BOMComponent, ProductionOrder


class BOMForm(forms.ModelForm):
    class Meta:
        model = BillOfMaterials
        fields = ['product', 'name', 'bom_type', 'quantity', 'estimated_time_minutes', 'notes']
        widgets = {
            'product': forms.Select(attrs={'class': 'form-select'}),
            'name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Ej: Receta principal'}),
            'bom_type': forms.Select(attrs={'class': 'form-select'}),
            'quantity': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.001', 'min': '0.001'}),
            'estimated_time_minutes': forms.NumberInput(attrs={'class': 'form-control', 'min': '0'}),
            'notes': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
        }


class BOMComponentForm(forms.ModelForm):
    class Meta:
        model = BOMComponent
        fields = ['component', 'quantity', 'unit', 'notes']
        widgets = {
            'component': forms.Select(attrs={'class': 'form-select'}),
            'quantity': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.001', 'min': '0.001'}),
            'unit': forms.Select(attrs={'class': 'form-select'}),
            'notes': forms.TextInput(attrs={'class': 'form-control'}),
        }


class ProductionOrderForm(forms.ModelForm):
    class Meta:
        model = ProductionOrder
        fields = ['number', 'bom', 'product', 'quantity', 'warehouse', 'priority', 'planned_date', 'sales_order', 'notes']
        widgets = {
            'number': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'OP-0001'}),
            'bom': forms.Select(attrs={'class': 'form-select'}),
            'product': forms.Select(attrs={'class': 'form-select'}),
            'quantity': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.001', 'min': '0.001'}),
            'warehouse': forms.Select(attrs={'class': 'form-select'}),
            'priority': forms.Select(attrs={'class': 'form-select'}),
            'planned_date': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'sales_order': forms.Select(attrs={'class': 'form-select'}),
            'notes': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
        }
