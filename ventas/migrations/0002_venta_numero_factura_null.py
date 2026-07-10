from django.db import migrations, models


class Migration(migrations.Migration):
    """
    Hace Venta.numero_factura nullable (null=True).
    Necesario para PostgreSQL: el patrón de save() que genera el número
    después de conocer el pk requiere insertar NULL primero, no '' (string
    vacío), para no colisionar con la restricción UNIQUE.
    """

    dependencies = [
        ('ventas', '0001_initial'),
    ]

    operations = [
        migrations.AlterField(
            model_name='venta',
            name='numero_factura',
            field=models.CharField(
                blank=True, max_length=20, null=True, unique=True,
                verbose_name='Número de factura',
            ),
        ),
    ]
