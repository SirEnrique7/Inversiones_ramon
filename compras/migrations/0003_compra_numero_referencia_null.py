from django.db import migrations, models


class Migration(migrations.Migration):
    """
    Hace Compra.numero_referencia nullable (null=True).
    Necesario para PostgreSQL: el patrón de save() que genera la referencia
    después de conocer el pk requiere insertar NULL primero, no '' (string
    vacío), para no colisionar con la restricción UNIQUE.
    """

    dependencies = [
        ('compras', '0002_initial'),
    ]

    operations = [
        migrations.AlterField(
            model_name='compra',
            name='numero_referencia',
            field=models.CharField(
                blank=True, max_length=30, null=True, unique=True,
                verbose_name='Referencia interna',
            ),
        ),
    ]
