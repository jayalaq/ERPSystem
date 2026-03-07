from django import forms
from .models import Customer, Supplier, Opportunity, Interaction, CustomerContact


class CustomerForm(forms.ModelForm):
    class Meta:
        model = Customer
        exclude = ['created_by', 'created_at', 'updated_at']
        widgets = {
            'customer_type': forms.Select(attrs={'class': 'form-select'}),
            'doc_type': forms.Select(attrs={'class': 'form-select'}),
            'doc_number': forms.TextInput(attrs={'class': 'form-control'}),
            'name': forms.TextInput(attrs={'class': 'form-control'}),
            'trade_name': forms.TextInput(attrs={'class': 'form-control'}),
            'email': forms.EmailInput(attrs={'class': 'form-control'}),
            'phone': forms.TextInput(attrs={'class': 'form-control'}),
            'mobile': forms.TextInput(attrs={'class': 'form-control'}),
            'address': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'department': forms.TextInput(attrs={'class': 'form-control'}),
            'province': forms.TextInput(attrs={'class': 'form-control'}),
            'district': forms.TextInput(attrs={'class': 'form-control'}),
            'credit_limit': forms.NumberInput(attrs={'class': 'form-control'}),
            'credit_days': forms.NumberInput(attrs={'class': 'form-control'}),
            'tags': forms.TextInput(attrs={'class': 'form-control'}),
            'notes': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'assigned_to': forms.Select(attrs={'class': 'form-select'}),
        }


class SupplierForm(forms.ModelForm):
    class Meta:
        model = Supplier
        exclude = ['created_at', 'updated_at']
        widgets = {
            'doc_type': forms.Select(attrs={'class': 'form-select'}),
            'doc_number': forms.TextInput(attrs={'class': 'form-control'}),
            'name': forms.TextInput(attrs={'class': 'form-control'}),
            'trade_name': forms.TextInput(attrs={'class': 'form-control'}),
            'email': forms.EmailInput(attrs={'class': 'form-control'}),
            'phone': forms.TextInput(attrs={'class': 'form-control'}),
            'address': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'contact_name': forms.TextInput(attrs={'class': 'form-control'}),
            'payment_terms': forms.NumberInput(attrs={'class': 'form-control'}),
            'bank_name': forms.TextInput(attrs={'class': 'form-control'}),
            'bank_account': forms.TextInput(attrs={'class': 'form-control'}),
            'bank_cci': forms.TextInput(attrs={'class': 'form-control'}),
        }


class OpportunityForm(forms.ModelForm):
    class Meta:
        model = Opportunity
        exclude = ['created_at', 'updated_at']
        widgets = {
            'customer': forms.Select(attrs={'class': 'form-select'}),
            'title': forms.TextInput(attrs={'class': 'form-control'}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'stage': forms.Select(attrs={'class': 'form-select'}),
            'priority': forms.Select(attrs={'class': 'form-select'}),
            'expected_amount': forms.NumberInput(attrs={'class': 'form-control'}),
            'probability': forms.NumberInput(attrs={'class': 'form-control', 'min': 0, 'max': 100}),
            'expected_close_date': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'assigned_to': forms.Select(attrs={'class': 'form-select'}),
            'source': forms.TextInput(attrs={'class': 'form-control'}),
        }


class InteractionForm(forms.ModelForm):
    class Meta:
        model = Interaction
        exclude = ['performed_by', 'created_at']
        widgets = {
            'customer': forms.Select(attrs={'class': 'form-select'}),
            'opportunity': forms.Select(attrs={'class': 'form-select'}),
            'interaction_type': forms.Select(attrs={'class': 'form-select'}),
            'subject': forms.TextInput(attrs={'class': 'form-control'}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'date': forms.DateTimeInput(attrs={'class': 'form-control', 'type': 'datetime-local'}),
            'next_action': forms.Textarea(attrs={'class': 'form-control', 'rows': 2}),
            'next_action_date': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
        }
