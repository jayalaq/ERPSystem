from django import forms
from .models import ContactMessage


class ContactForm(forms.ModelForm):
    class Meta:
        model = ContactMessage
        fields = ['name', 'email', 'phone', 'company', 'ruc', 'service_interest', 'message']
        widgets = {
            'name': forms.TextInput(attrs={
                'class': 'form-control', 'placeholder': 'Tu nombre completo',
            }),
            'email': forms.EmailInput(attrs={
                'class': 'form-control', 'placeholder': 'correo@empresa.com',
            }),
            'phone': forms.TextInput(attrs={
                'class': 'form-control', 'placeholder': '+51 999 999 999',
            }),
            'company': forms.TextInput(attrs={
                'class': 'form-control', 'placeholder': 'Nombre de tu empresa',
            }),
            'ruc': forms.TextInput(attrs={
                'class': 'form-control', 'placeholder': '20XXXXXXXXX',
            }),
            'service_interest': forms.Select(attrs={
                'class': 'form-select',
            }),
            'message': forms.Textarea(attrs={
                'class': 'form-control', 'rows': 4,
                'placeholder': 'Cuéntanos sobre tu proyecto o necesidad...',
            }),
        }
