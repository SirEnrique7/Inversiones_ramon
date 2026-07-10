from django import forms
from .models import Producto, Categoria, Proveedor, SolicitudInventario


class ProductoForm(forms.ModelForm):
    class Meta:
        model  = Producto
        fields = [
            'nombre', 'descripcion', 'categoria', 'proveedor',
            'precio_compra', 'precio_venta',
            'stock_actual', 'stock_minimo', 'dias_cobertura', 'activo'
        ]
        widgets = {
            'nombre':         forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Nombre del producto'}),
            'descripcion':    forms.Textarea(attrs={'class': 'form-control', 'rows': 3, 'placeholder': 'Descripción opcional'}),
            'categoria':      forms.Select(attrs={'class': 'form-select'}),
            'proveedor':      forms.Select(attrs={'class': 'form-select'}),
            'precio_compra':  forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01', 'min': '0'}),
            'precio_venta':   forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01', 'min': '0'}),
            'stock_actual':   forms.NumberInput(attrs={'class': 'form-control', 'min': '0'}),
            'stock_minimo':   forms.NumberInput(attrs={'class': 'form-control', 'min': '1'}),
            'dias_cobertura': forms.NumberInput(attrs={'class': 'form-control', 'min': '1', 'max': '30'}),
            'activo':         forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }
        labels = {
            'nombre':         'Nombre',
            'descripcion':    'Descripción',
            'categoria':      'Categoría',
            'proveedor':      'Proveedor',
            'precio_compra': 'Precio de compra (Bs)',
            'precio_venta':  'Precio de venta (Bs)',
            'stock_actual':  'Stock actual',
            'stock_minimo':  'Stock mínimo',
            'dias_cobertura': 'Días de cobertura',
            'activo':         'Producto activo',
        }

    def clean(self):
        cleaned = super().clean()
        compra = cleaned.get('precio_compra')
        venta  = cleaned.get('precio_venta')
        if compra and venta and venta <= compra:
            raise forms.ValidationError(
                'El precio de venta debe ser mayor al precio de compra.'
            )
        return cleaned


class CategoriaForm(forms.ModelForm):
    class Meta:
        model  = Categoria
        fields = ['nombre', 'descripcion']
        widgets = {
            'nombre':      forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Nombre de la categoría'}),
            'descripcion': forms.Textarea(attrs={'class': 'form-control', 'rows': 2}),
        }


class ProveedorForm(forms.ModelForm):
    class Meta:
        model  = Proveedor
        # Se incluye 'activo' para permitir el control de baja lógica desde el formulario
        fields = ['nombre', 'rif', 'empresa', 'telefono', 'direccion', 'dia_visita', 'activo']
        widgets = {
            'nombre':     forms.TextInput(attrs={'class': 'form-control'}),
            'rif':        forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'J-XXXXXXXX-X'}),
            'empresa':    forms.TextInput(attrs={'class': 'form-control'}),
            'telefono':   forms.TextInput(attrs={'class': 'form-control'}),
            'direccion':  forms.Textarea(attrs={'class': 'form-control', 'rows': 2}),
            'dia_visita': forms.Select(attrs={'class': 'form-select'}),
            'activo':     forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }
        labels = {
            'nombre':     'Nombre / Razón Social',
            'rif':        'RIF',
            'empresa':    'Empresa',
            'telefono':   'Teléfono',
            'direccion':  'Dirección',
            'dia_visita': 'Día de visita',
            'activo':     'Proveedor activo',
        }

    def clean_rif(self):
        import re
        rif = self.cleaned_data.get('rif', '').strip().upper().replace('.', '')
        if not re.match(r'^[VJGE]-\d{6,12}(-\d)?$', rif):
            raise forms.ValidationError(
                'El formato del RIF no es válido. Ejemplos: J-12345678-9, V-12345678.'
            )
        # Verificar duplicado excluyendo la instancia actual
        qs = Proveedor.objects.filter(rif=rif)
        if self.instance and self.instance.pk:
            qs = qs.exclude(pk=self.instance.pk)
        if qs.exists():
            raise forms.ValidationError('Ya existe un proveedor registrado con este RIF.')
        return rif


class SolicitudInventarioForm(forms.ModelForm):
    class Meta:
        model  = SolicitudInventario
        fields = ['producto', 'cantidad_solicitada', 'observacion']
        widgets = {
            'producto':            forms.Select(attrs={'class': 'form-select'}),
            'cantidad_solicitada': forms.NumberInput(attrs={'class': 'form-control', 'min': '1'}),
            'observacion':         forms.Textarea(attrs={'class': 'form-control', 'rows': 3,
                                                         'placeholder': 'Motivo o nota adicional (opcional)'}),
        }
        labels = {
            'producto':            'Producto',
            'cantidad_solicitada': 'Cantidad a solicitar',
            'observacion':         'Observación',
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        producto_field = self.fields.get('producto')
        # Validación estricta de tipo para blindar a Pylance contra advertencias de atributos dinámicos
        if isinstance(producto_field, forms.ModelChoiceField):
            producto_field.queryset = Producto.objects.filter(activo=True).order_by('nombre')


class ResponderSolicitudForm(forms.Form):
    DECISION_CHOICES = [
        ('aprobada',  'Aprobar'),
        ('rechazada', 'Rechazar'),
    ]
    # Se añade la clase 'form-check-input' para unificar la estética de los RadioSelect en todo el sistema
    decision    = forms.ChoiceField(
        choices=DECISION_CHOICES, 
        widget=forms.RadioSelect(attrs={'class': 'form-check-input'})
    )
    observacion = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={'class': 'form-control', 'rows': 2,
                                    'placeholder': 'Razón del rechazo u observación (opcional)'})
    )