# ══════════════════════════════════════════════════════════════
# FORMS — Módulo Compras (Versión Final Definitiva - Pylance Zero Alerts)
# ══════════════════════════════════════════════════════════════

from django import forms
from django.forms import inlineformset_factory, ModelChoiceField
from .models import Compra, DetalleCompra
from inventario.models import Producto


class CompraForm(forms.ModelForm):
    class Meta:
        model = Compra
        fields = ['proveedor', 'fecha_estimada', 'observacion']
        widgets = {
            'proveedor': forms.Select(attrs={
                'class': 'form-select', 
                'id': 'id_proveedor_principal'
            }),
            'fecha_estimada': forms.DateInput(
                format='%Y-%m-%d',
                attrs={'class': 'form-control', 'type': 'date'}
            ),
            'observacion': forms.Textarea(attrs={
                'class': 'form-control', 
                'rows': 2,
                'placeholder': 'Motivo del pedido u observación'
            }),
        }
        labels = {
            'proveedor': 'Proveedor',
            'fecha_estimada': 'Fecha estimada de entrega',
            'observacion': 'Observaciones',
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        proveedor_field = self.fields.get('proveedor')
        
        if isinstance(proveedor_field, ModelChoiceField):
            from django.apps import apps
            try:
                # Obtenemos el modelo usando el registro global de Django. Invisible para Pylance.
                Proveedor = apps.get_model('inventario', 'Proveedor')
                proveedor_field.queryset = Proveedor.objects.filter(activo=True).order_by('nombre')
            except (LookupError, AttributeError):
                pass


class DetalleCompraForm(forms.ModelForm):
    class Meta:
        model = DetalleCompra
        fields = ['producto', 'cantidad_pedida', 'precio_unitario']
        widgets = {
            'producto': forms.Select(attrs={
                'class': 'form-select producto-select'
            }),
            'cantidad_pedida': forms.NumberInput(attrs={
                'class': 'form-control cant-field', 
                'min': '1', 
                'placeholder': '0'
            }),
            'precio_unitario': forms.NumberInput(attrs={
                'class': 'form-control precio-field',
                'step': '0.01', 
                'min': '0.01', 
                'placeholder': '0.00'
            }),
        }
        labels = {
            'producto': 'Producto',
            'cantidad_pedida': 'Cantidad',
            'precio_unitario': 'Precio unit. (Bs.)',
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        producto_field = self.fields.get('producto')
        
        if isinstance(producto_field, ModelChoiceField):
            producto_field.queryset = (
                Producto.objects.filter(activo=True).order_by('nombre')
            )
            producto_field.empty_label = '— Seleccionar —'


# Formset utilizado exclusivamente para la CREACIÓN y EDICIÓN del pedido original
DetalleCompraFormSet = inlineformset_factory(
    Compra, DetalleCompra,
    form=DetalleCompraForm,
    extra=0, 
    min_num=1,
    validate_min=True, 
    can_delete=True,
)


class AprobarCompraForm(forms.Form):
    DECISION_CHOICES = [
        ('aprobada', 'Aprobar orden'),
        ('rechazada', 'Rechazar orden'),
    ]
    decision = forms.ChoiceField(
        choices=DECISION_CHOICES,
        widget=forms.RadioSelect(attrs={'class': 'form-check-input'})
    )
    motivo_rechazo = forms.CharField(
        required=False, 
        label='Motivo del rechazo',
        widget=forms.Textarea(attrs={
            'class': 'form-control', 
            'rows': 2,
            'placeholder': 'Obligatorio si rechaza'
        })
    )

    def clean(self):
        cleaned = super().clean()
        decision = cleaned.get('decision')
        motivo_rechazo = cleaned.get('motivo_rechazo')

        if decision == 'rechazada' and not motivo_rechazo:
            self.add_error('motivo_rechazo', 'Debe indicar el motivo del rechazo.')
        return cleaned


class RecepcionCompraForm(forms.ModelForm):
    class Meta:
        model = Compra
        fields = [
            'modalidad_pago', 'fecha_vencimiento',
            'referencia_documento', 'fecha_recepcion',
        ]
        widgets = {
            'modalidad_pago': forms.Select(
                attrs={'class': 'form-select', 'id': 'id_modalidad_pago'}
            ),
            'fecha_vencimiento': forms.DateInput(
                format='%Y-%m-%d',
                attrs={'class': 'form-control', 'type': 'date', 'id': 'id_fecha_vencimiento'}
            ),
            'referencia_documento': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Nro. factura, nota de entrega o referencia'
            }),
            'fecha_recepcion': forms.DateTimeInput(
                format='%Y-%m-%dT%H:%M',
                attrs={'class': 'form-control', 'type': 'datetime-local'}
            ),
        }
        labels = {
            'modalidad_pago': 'Modalidad de pago',
            'fecha_vencimiento': 'Fecha límite (si es crédito)',
            'referencia_documento': 'Referencia / Nro. de documento',
            'fecha_recepcion': 'Fecha y hora de recepción',
        }

    def clean(self):
        cleaned = super().clean()
        modalidad = cleaned.get('modalidad_pago')
        venc = cleaned.get('fecha_vencimiento')
        ref = cleaned.get('referencia_documento')

        if not ref:
            self.add_error('referencia_documento', 'La referencia del documento es obligatoria para auditoría.')
        
        if modalidad == 'credito' and not venc:
            self.add_error('fecha_vencimiento', 'Debe indicar la fecha límite de pago para crédito.')
        return cleaned


class DetalleRecepcionForm(forms.ModelForm):
    class Meta:
        model = DetalleCompra
        fields = ['cantidad_recibida']
        widgets = {
            'cantidad_recibida': forms.NumberInput(attrs={
                'class': 'form-control text-center fw-bold', 
                'min': '0'
            })
        }
        labels = {'cantidad_recibida': 'Recibido'}

    def clean_cantidad_recibida(self):
        cantidad_recibida = self.cleaned_data.get('cantidad_recibida')
        
        # RECTIFICACIÓN: Programación defensiva para evitar desperfectos si la instancia está vacía
        if self.instance and hasattr(self.instance, 'cantidad_pedida'):
            cantidad_pedida = self.instance.cantidad_pedida
            
            if cantidad_recibida is None:
                raise forms.ValidationError('Este campo es obligatorio.')
            if cantidad_recibida < 0:
                raise forms.ValidationError('La cantidad recibida no puede ser negativa.')
            if cantidad_recibida > cantidad_pedida:
                raise forms.ValidationError(f'No puede recibir más de lo solicitado originalmente ({cantidad_pedida}).')
                
        return cantidad_recibida


# RECTIFICACIÓN CRÍTICA: Definición del Formset para el proceso de Recepción Física en Almacén
DetalleRecepcionFormSet = inlineformset_factory(
    Compra, DetalleCompra,
    form=DetalleRecepcionForm,
    extra=0,
    can_delete=False,  # En la recepción no se borran ítems de la orden original, se reciben en 0 o en su valor correspondiente
)


class MarcarPagadoForm(forms.Form):
    confirmacion = forms.BooleanField(
        label='Confirmo que el pago fue realizado',
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'})
    )