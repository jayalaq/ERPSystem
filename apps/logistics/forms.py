from django import forms
from django.core.exceptions import ValidationError
from .models import Product, Warehouse, StockMovement, PurchaseOrder, DispatchGuide

MAX_IMAGE_SIZE = 5 * 1024 * 1024  # 5 MB
ALLOWED_IMAGE_TYPES = ['image/jpeg', 'image/png', 'image/webp', 'image/gif']


class ProductForm(forms.ModelForm):
    class Meta:
        model = Product
        exclude = ['created_at', 'updated_at']
        widgets = {
            'product_type': forms.Select(attrs={'class': 'form-select'}),
            'sku': forms.TextInput(attrs={'class': 'form-control'}),
            'barcode': forms.TextInput(attrs={'class': 'form-control'}),
            'name': forms.TextInput(attrs={'class': 'form-control'}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'category': forms.Select(attrs={'class': 'form-select'}),
            'brand': forms.Select(attrs={'class': 'form-select'}),
            'unit': forms.Select(attrs={'class': 'form-select'}),
            'affectation_type': forms.Select(attrs={'class': 'form-select'}),
            'purchase_price': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
            'sale_price': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
            'wholesale_price': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
            'minimum_price': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
            'min_stock': forms.NumberInput(attrs={'class': 'form-control'}),
            'max_stock': forms.NumberInput(attrs={'class': 'form-control'}),
        }

    def clean_image(self):
        image = self.cleaned_data.get('image')
        if image and hasattr(image, 'size'):
            if image.size > MAX_IMAGE_SIZE:
                raise ValidationError(
                    f'La imagen no debe superar {MAX_IMAGE_SIZE // (1024 * 1024)} MB. '
                    f'Tamaño actual: {image.size / (1024 * 1024):.1f} MB.'
                )
            if hasattr(image, 'content_type') and image.content_type not in ALLOWED_IMAGE_TYPES:
                raise ValidationError(
                    f'Formato de imagen no soportado: {image.content_type}. '
                    f'Formatos permitidos: JPEG, PNG, WebP, GIF.'
                )
        return image


class WarehouseForm(forms.ModelForm):
    class Meta:
        model = Warehouse
        exclude = ['created_at']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control'}),
            'code': forms.TextInput(attrs={'class': 'form-control'}),
            'address': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'branch': forms.Select(attrs={'class': 'form-select'}),
            'manager': forms.Select(attrs={'class': 'form-select'}),
        }


class StockMovementForm(forms.ModelForm):
    class Meta:
        model = StockMovement
        exclude = ['performed_by', 'created_at', 'reference_type', 'reference_id']
        widgets = {
            'movement_type': forms.Select(attrs={'class': 'form-select'}),
            'product': forms.Select(attrs={'class': 'form-select'}),
            'warehouse': forms.Select(attrs={'class': 'form-select'}),
            'destination_warehouse': forms.Select(attrs={'class': 'form-select'}),
            'quantity': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.001'}),
            'unit_cost': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
            'reference': forms.TextInput(attrs={'class': 'form-control'}),
            'reason': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
        }


class PurchaseOrderForm(forms.ModelForm):
    class Meta:
        model = PurchaseOrder
        exclude = ['created_by', 'created_at', 'updated_at']
        widgets = {
            'number': forms.TextInput(attrs={'class': 'form-control'}),
            'supplier': forms.Select(attrs={'class': 'form-select'}),
            'warehouse': forms.Select(attrs={'class': 'form-select'}),
            'status': forms.Select(attrs={'class': 'form-select'}),
            'order_date': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'expected_date': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'subtotal': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
            'igv': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
            'total': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
            'notes': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
        }


class DispatchGuideForm(forms.ModelForm):
    class Meta:
        model = DispatchGuide
        exclude = ['created_by', 'created_at', 'updated_at']
        widgets = {
            'guide_type': forms.Select(attrs={'class': 'form-select'}),
            'series': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'T001'}),
            'correlative': forms.NumberInput(attrs={'class': 'form-control'}),
            'issue_date': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'transfer_start_date': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'transfer_reason': forms.Select(attrs={'class': 'form-select'}),
            'description': forms.TextInput(attrs={'class': 'form-control'}),
            'origin_address': forms.Textarea(attrs={'class': 'form-control', 'rows': 2}),
            'origin_ubigeo': forms.TextInput(attrs={'class': 'form-control'}),
            'destination_address': forms.Textarea(attrs={'class': 'form-control', 'rows': 2}),
            'destination_ubigeo': forms.TextInput(attrs={'class': 'form-control'}),
            'recipient': forms.Select(attrs={'class': 'form-select'}),
            'carrier_name': forms.TextInput(attrs={'class': 'form-control'}),
            'carrier_ruc': forms.TextInput(attrs={'class': 'form-control'}),
            'driver_name': forms.TextInput(attrs={'class': 'form-control'}),
            'driver_license': forms.TextInput(attrs={'class': 'form-control'}),
            'vehicle_plate': forms.TextInput(attrs={'class': 'form-control'}),
            'gross_weight': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.001'}),
            'packages': forms.NumberInput(attrs={'class': 'form-control'}),
            'related_invoice': forms.Select(attrs={'class': 'form-select'}),
            'status': forms.Select(attrs={'class': 'form-select'}),
            'notes': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
        }
