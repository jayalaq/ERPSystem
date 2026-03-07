from django import forms
from .models import Invoice, InvoiceItem, PaymentRecord, AccountPayable, DocumentSeries


class InvoiceForm(forms.ModelForm):
    class Meta:
        model = Invoice
        fields = ['doc_type', 'series', 'issue_date', 'due_date', 'customer',
                  'payment_condition', 'notes']
        widgets = {
            'doc_type': forms.Select(attrs={'class': 'form-select'}),
            'series': forms.TextInput(attrs={'class': 'form-control'}),
            'issue_date': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'due_date': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'customer': forms.Select(attrs={'class': 'form-select'}),
            'payment_condition': forms.Select(attrs={'class': 'form-select'}),
            'notes': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
        }


class InvoiceItemForm(forms.ModelForm):
    class Meta:
        model = InvoiceItem
        exclude = ['invoice']
        widgets = {
            'product': forms.Select(attrs={'class': 'form-select'}),
            'description': forms.TextInput(attrs={'class': 'form-control'}),
            'unit': forms.Select(attrs={'class': 'form-select'}),
            'quantity': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.001'}),
            'unit_price': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
            'discount': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
        }


class PaymentRecordForm(forms.ModelForm):
    class Meta:
        model = PaymentRecord
        exclude = ['recorded_by', 'created_at']
        widgets = {
            'invoice': forms.Select(attrs={'class': 'form-select'}),
            'payment_date': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'amount': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
            'payment_method': forms.Select(attrs={'class': 'form-select'}),
            'reference': forms.TextInput(attrs={'class': 'form-control'}),
            'notes': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
        }


class DocumentSeriesForm(forms.ModelForm):
    class Meta:
        model = DocumentSeries
        fields = '__all__'
        widgets = {
            'doc_type': forms.Select(attrs={'class': 'form-select'}),
            'series': forms.TextInput(attrs={'class': 'form-control'}),
            'next_correlative': forms.NumberInput(attrs={'class': 'form-control'}),
            'branch': forms.Select(attrs={'class': 'form-select'}),
        }
