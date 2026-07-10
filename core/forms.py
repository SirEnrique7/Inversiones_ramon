# ══════════════════════════════════════════════════════════════
# FORMS — Módulo Core (Usuarios + Auth)
# ══════════════════════════════════════════════════════════════

from django import forms
from django.contrib.auth.forms import (
    AuthenticationForm, PasswordResetForm, SetPasswordForm
)
from django.core.exceptions import ValidationError
from .models import Usuario
import re

# ─────────────────────────────────────────────
# 1. LOGIN personalizado
# ─────────────────────────────────────────────

class LoginForm(AuthenticationForm):
    username = forms.CharField(
        label='Usuario',
        widget=forms.TextInput(attrs={
            'class':       'form-control form-control-lg',
            'placeholder': 'Nombre de usuario',
            'autofocus':   True,
        })
    )
    password = forms.CharField(
        label='Contraseña',
        widget=forms.PasswordInput(attrs={
            'class':       'form-control form-control-lg',
            'placeholder': 'Contraseña',
        })
    )


# ─────────────────────────────────────────────
# 2. Alta de usuario (solo Admin)
# ─────────────────────────────────────────────

class UsuarioCrearForm(forms.ModelForm):
    password1 = forms.CharField(
        label='Contraseña',
        widget=forms.PasswordInput(attrs={'class': 'form-control'}),
        help_text='Mínimo 8 caracteres, alfanumérica.'
    )
    password2 = forms.CharField(
        label='Confirmar contraseña',
        widget=forms.PasswordInput(attrs={'class': 'form-control'})
    )

    class Meta:
        model  = Usuario
        fields = ['first_name', 'last_name', 'cedula', 'email', 'telefono', 'username', 'rol']
        widgets = {
            'first_name': forms.TextInput(attrs={'class': 'form-control'}),
            'last_name':  forms.TextInput(attrs={'class': 'form-control'}),
            'cedula':     forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'V-00000000'}),
            'email':      forms.EmailInput(attrs={'class': 'form-control'}),
            'telefono':   forms.TextInput(attrs={'class': 'form-control', 'placeholder': '0414-0000000'}),
            'username':   forms.TextInput(attrs={'class': 'form-control'}),
            'rol':        forms.Select(attrs={'class': 'form-select'}),
        }
        labels = {
            'first_name': 'Nombre',
            'last_name':  'Apellido',
            'cedula':     'Cédula de identidad',
            'email':      'Correo electrónico',
            'telefono':   'Teléfono',
            'username':   'Nombre de usuario',
            'rol':        'Rol',
        }

    def clean_password2(self):
        p1 = self.cleaned_data.get('password1', '')
        p2 = self.cleaned_data.get('password2', '')
        if p1 != p2:
            raise ValidationError('Las contraseñas no coinciden.')
        if len(p1) < 8:
            raise ValidationError('La contraseña debe tener al menos 8 caracteres.')
        # Verificación correcta: exigir que tenga AL MENOS una letra Y un dígito.
        # La forma anterior (isdigit() or isalpha()) permitía contraseñas de puros símbolos.
        if not any(c.isalpha() for c in p1) or not any(c.isdigit() for c in p1):
            raise ValidationError('La contraseña debe contener letras y números.')
        return p2

    def clean_email(self):
        email = self.cleaned_data.get('email', '').strip().lower()
        if Usuario.objects.filter(email=email).exists():
            raise ValidationError('Ya existe un usuario con este correo.')
        return email

    def clean_cedula(self):
        cedula = self.cleaned_data.get('cedula', '')
        
        # 1. Limpiamos y estandarizamos (mayúsculas y sin espacios)
        cedula = cedula.upper().strip()
        
        # 2. Validamos el formato con la expresión regular
        if not re.match(r'^[VEJ]-\d+$', cedula):
            raise ValidationError('El formato debe ser V-12345678, E-12345678 o J-12345678.')
        
        # 3. Consultamos la base de datos (búsqueda general)
        if Usuario.objects.filter(cedula=cedula).exists():
            raise ValidationError('Ya existe un usuario con esta cédula.')
            
        return cedula

    def save(self, commit=True):
        usuario = super().save(commit=False)
        usuario.set_password(self.cleaned_data['password1'])
        if commit:
            usuario.save()
        return usuario


# ─────────────────────────────────────────────
# 3. Edición de usuario (solo Admin)
# ─────────────────────────────────────────────

class UsuarioEditarForm(forms.ModelForm):
    class Meta:
        model  = Usuario
        fields = ['first_name', 'last_name', 'cedula', 'email', 'telefono', 'rol']
        widgets = {
            'first_name': forms.TextInput(attrs={'class': 'form-control'}),
            'last_name':  forms.TextInput(attrs={'class': 'form-control'}),
            'cedula':     forms.TextInput(attrs={'class': 'form-control'}),
            'email':      forms.EmailInput(attrs={'class': 'form-control'}),
            'telefono':   forms.TextInput(attrs={'class': 'form-control'}),
            'rol':        forms.Select(attrs={'class': 'form-select'}),
        }
        labels = {
            'first_name': 'Nombre',
            'last_name':  'Apellido',
            'cedula':     'Cédula',
            'email':      'Correo electrónico',
            'telefono':   'Teléfono',
            'rol':        'Rol',
        }

    def clean_email(self):
        email = self.cleaned_data.get('email', '').strip().lower()
        qs = Usuario.objects.filter(email=email).exclude(pk=self.instance.pk)
        if qs.exists():
            raise ValidationError('Ya existe otro usuario con este correo.')
        return email
    
    def clean_cedula(self):
        cedula = self.cleaned_data.get('cedula', '')
        
        # 1. Limpiamos y estandarizamos (mayúsculas y sin espacios accidentales)
        cedula = cedula.upper().strip()
        
        # 2. Validamos el formato
        if not re.match(r'^[VEJ]-\d+$', cedula):
            raise ValidationError('El formato debe ser V-12345678, E-12345678 o J-12345678.')
        
        # 3. Consultamos la base de datos usando la cédula ya corregida
        qs = Usuario.objects.filter(cedula=cedula).exclude(pk=self.instance.pk)
        if qs.exists():
            raise ValidationError('Ya existe otro usuario con esta cédula.')
            
        return cedula


# ─────────────────────────────────────────────
# 4. Recuperación de contraseña (email)
# ─────────────────────────────────────────────

class RecuperarPasswordForm(PasswordResetForm):
    email = forms.EmailField(
        label='Correo electrónico institucional',
        widget=forms.EmailInput(attrs={
            'class':       'form-control form-control-lg',
            'placeholder': 'tucorreo@empresa.com',
        })
    )

    def clean_email(self):
        # Solo normalizar — NO validar existencia aquí.
        # La vista lo maneja silenciosamente para evitar enumeración de correos.
        return self.cleaned_data.get('email', '').strip().lower()


# ─────────────────────────────────────────────
# 5. Nueva contraseña (desde el enlace del correo)
# ─────────────────────────────────────────────

class NuevaPasswordForm(SetPasswordForm):
    new_password1 = forms.CharField(
        label='Nueva contraseña',
        widget=forms.PasswordInput(attrs={
            'class':       'form-control form-control-lg',
            'placeholder': 'Nueva contraseña',
        }),
        help_text='Mínimo 8 caracteres, alfanumérica.'
    )
    new_password2 = forms.CharField(
        label='Confirmar contraseña',
        widget=forms.PasswordInput(attrs={
            'class':       'form-control form-control-lg',
            'placeholder': 'Repite la contraseña',
        })
    )
