from django.db import migrations, models


class Migration(migrations.Migration):
    """
    Hace Producto.codigo nullable (null=True).
    Necesario para PostgreSQL: el patrón de save() que genera el código
    después de conocer el pk requiere insertar NULL primero, no '' (string
    vacío), para no colisionar con la restricción UNIQUE.
    """

    dependencies = [
        ('inventario', '0002_proveedor_activo'),
    ]

    operations = [
        migrations.AlterField(
            model_name='producto',
            name='codigo',
            field=models.CharField(
                blank=True, max_length=20, null=True, unique=True,
            ),
        ),
    ]
