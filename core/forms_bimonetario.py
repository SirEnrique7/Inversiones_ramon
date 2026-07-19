from django import forms
from django.core.exceptions import ValidationError
from django.core.validators import RegexValidator, MinLengthValidator, MaxLengthValidator
from decimal import Decimal, InvalidOperation
import re
from .models_bimonetario import CuentaPorPagar, CuentaPorCobrar, Cliente


# ─────────────────────────────────────────────
# ABONO A PROVEEDOR (CUENTAS POR PAGAR)
# ─────────────────────────────────────────────

class AbonoProveedorForm(forms.Form):
    monto_bs = forms.DecimalField(
        label='Monto a pagar (Bs.)',
        min_value=Decimal('0.01'),
        max_digits=14, decimal_places=2,
        widget=forms.NumberInput(attrs={
            'class': 'form-control form-control-lg fw-bold text-danger',
            'step': '0.01', 'placeholder': '0.00'
        })
    )
    # INYECCIÓN BIMONETARIA: Captura la tasa para congelar el valor histórico
    tasa_bcv = forms.DecimalField(
        label='Tasa BCV del día',
        min_value=Decimal('0.01'),
        max_digits=8, decimal_places=4,
        widget=forms.NumberInput(attrs={
            'class': 'form-control', 'step': '0.0001', 'readonly': 'readonly'
        }),
        help_text="Tasa oficial del Banco Central de Venezuela al momento del pago."
    )
    referencia = forms.CharField(
        label='Referencia bancaria / legal',
        validators=[
            RegexValidator(
                regex=r'^\d+$',
                message='La referencia debe contener solo números.'
            ),
            MinLengthValidator(4, message='La referencia debe tener al menos 4 dígitos.'),
            MaxLengthValidator(21, message='La referencia no puede exceder los 21 dígitos.')
        ],
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Nro. de transferencia, operación o nota de entrega',
            'inputmode': 'numeric',
            'maxlength': '21',
        })
    )

    def __init__(self, *args, cuenta=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.cuenta = cuenta

    def clean_tasa_bcv(self):
        tasa = self.cleaned_data.get('tasa_bcv')
        if not tasa:
            raise ValidationError(
                'No hay tasa BCV registrada para hoy. '
                'Un administrador debe actualizarla antes de registrar pagos.'
            )
        return tasa

    def clean_monto_bs(self):
        # CORRECCIÓN: .get() evita el KeyError si el campo no pasa las reglas base de Django
        monto = self.cleaned_data.get('monto_bs')
        if monto is None:
            return monto
            
        if self.cuenta and monto > self.cuenta.saldo_restante:
            raise ValidationError(
                f'El monto introducido supera el saldo restante de la cuenta '
                f'(Bs. {self.cuenta.saldo_restante:,.2f}).'
            )
        return monto


# ─────────────────────────────────────────────
# PAGO DE CLIENTE (CUENTAS POR COBRAR)
# ─────────────────────────────────────────────

class PagoClienteForm(forms.Form):
    monto_bs = forms.DecimalField(
        label='Monto recibido (Bs.)',
        min_value=Decimal('0.01'),
        max_digits=14, decimal_places=2,
        widget=forms.NumberInput(attrs={
            'class': 'form-control form-control-lg fw-bold text-success',
            'step': '0.01', 'placeholder': '0.00'
        })
    )
    # INYECCIÓN BIMONETARIA: Captura la tasa para congelar el valor histórico
    tasa_bcv = forms.DecimalField(
        label='Tasa BCV del día',
        min_value=Decimal('0.01'),
        max_digits=8, decimal_places=4,
        widget=forms.NumberInput(attrs={
            'class': 'form-control', 'step': '0.0001', 'readonly': 'readonly'
        })
    )
    referencia = forms.CharField(
        label='Referencia bancaria / legal',
        validators=[
            RegexValidator(
                regex=r'^\d+$',
                message='La referencia debe contener solo números.'
            ),
            MinLengthValidator(4, message='La referencia debe tener al menos 4 dígitos.'),
            MaxLengthValidator(21, message='La referencia no puede exceder los 21 dígitos.')
        ],
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Nro. de transferencia o pago móvil',
            'inputmode': 'numeric',
            'maxlength': '21',
        })
    )

    def __init__(self, *args, cuenta=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.cuenta = cuenta

    def clean_tasa_bcv(self):
        tasa = self.cleaned_data.get('tasa_bcv')
        if not tasa:
            raise ValidationError(
                'No hay tasa BCV registrada para hoy. '
                'Un administrador debe actualizarla antes de registrar pagos.'
            )
        return tasa

    def clean_monto_bs(self):
        # CORRECCIÓN: .get() seguro
        monto = self.cleaned_data.get('monto_bs')
        if monto is None:
            return monto
            
        if self.cuenta and monto > self.cuenta.saldo_restante:
            raise ValidationError(
                f'El monto recibido supera el saldo pendiente de cobro '
                f'(Bs. {self.cuenta.saldo_restante:,.2f}).'
            )
        return monto


# ─────────────────────────────────────────────
# CLIENTE
# ─────────────────────────────────────────────

class ClienteForm(forms.ModelForm):
    class Meta:
        model = Cliente
        fields = ['cedula_rif', 'nombre', 'apellido', 'telefono', 'direccion']
        widgets = {
            'cedula_rif': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Ej: V-12345678 o J-12345678-0'
            }),
            'nombre': forms.TextInput(attrs={'class': 'form-control'}),
            'apellido': forms.TextInput(attrs={'class': 'form-control'}),
            'telefono': forms.TextInput(attrs={
                'class': 'form-control', 'placeholder': '0414-1234567'
            }),
            'direccion': forms.Textarea(attrs={'class': 'form-control', 'rows': 2}),
        }
        labels = {
            'cedula_rif': 'Cédula / RIF',
            'nombre': 'Nombre',
            'apellido': 'Apellido',
            'telefono': 'Teléfono',
            'direccion': 'Dirección',
        }

    def clean_cedula_rif(self):
        # CORRECCIÓN: Sanitización de datos legales para consistencia en BD
        data = self.cleaned_data.get('cedula_rif', '').strip().upper()
        
        # Elimina puntos intermedios comunes que dañan las búsquedas (ej: V-12.345.678 -> V-12345678)
        data = data.replace('.', '')
        
        # Validación mediante expresión regular para asegurar el formato venezolano estándar
        if not re.match(r'^[VJGE]-\d{6,12}$', data):
            raise ValidationError(
                'El formato de la Cédula o RIF no es válido. '
                'Ejemplos correctos: V-12345678, J-123456789, E-12345678.'
            )
            
        # Validar duplicados de forma manual para evitar excepciones feas de la BD en actualizaciones/creaciones
        id_existente = Cliente.objects.filter(cedula_rif=data).exclude(pk=self.instance.pk).exists()
        if id_existente:
            raise ValidationError('Ya existe un cliente registrado con esta Cédula / RIF.')
            
        return data