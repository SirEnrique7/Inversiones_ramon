# Guía de Migración a PostgreSQL

## Resumen de cambios incluidos

| Archivo | Cambio |
|---|---|
| `requirements.txt` | `psycopg2-binary` activado |
| `settings.py` | `DATABASES` usa **únicamente PostgreSQL**, configurado vía `.env` (obligatorio: `DB_NAME`, `DB_USER`, `DB_PASSWORD`). Sin `.env`, el sistema no arranca y dice exactamente qué falta |
| `inventario/models.py` | `Producto.codigo` → `null=True`; `save()` corregido |
| `ventas/models.py` | `Venta.numero_factura` → `null=True`; `save()` corregido |
| `compras/models.py` | `Compra.numero_referencia` → `null=True`; `save()` corregido |
| `inventario/migrations/0003_producto_codigo_null.py` | Migración del campo |
| `ventas/migrations/0002_venta_numero_factura_null.py` | Migración del campo |
| `compras/migrations/0003_compra_numero_referencia_null.py` | Migración del campo |
| `.env.example` | Plantilla de variables de entorno, incluye `CSRF_TRUSTED_ORIGINS` y `BEHIND_PROXY` |
| `inversiones_ramon/settings_prod.py` | `SECURE_PROXY_SSL_HEADER` (evita loop de redirección HTTPS detrás de Nginx), `CSRF_TRUSTED_ORIGINS`, logging tolerante a fallos de permisos |
| `core/context_processors.py` | `tasa_bcv` ya no puede dejar caer una excepción (ni siquiera si la BD está caída), evitando que falle también la página de error 500 |
| `compras/views.py` | Import faltante de `Producto` que rompía la recepción de órdenes de compra |
| `MIGRACION_POSTGRESQL.md` | Pasos 5-6 reordenados: `createsuperuser` y `loaddata` ya no colisionan; `dumpdata` excluye `admin.logentry` y `sessions` |

---

## Paso 1 — Instalar dependencias

```bash
pip install -r requirements.txt
```

---

## Paso 2 — Crear la base de datos en PostgreSQL

```sql
-- Conectado como superusuario (psql -U postgres)
CREATE USER ramon_user WITH PASSWORD 'tu_password_seguro';
CREATE DATABASE inversiones_ramon OWNER ramon_user;
GRANT ALL PRIVILEGES ON DATABASE inversiones_ramon TO ramon_user;
```

---

## Paso 3 — Configurar el entorno

```bash
# Copiar la plantilla
cp .env.example .env
```

Editar `.env` con los valores reales:

```
DB_NAME=inversiones_ramon
DB_USER=ramon_user
DB_PASSWORD=tu_password_seguro
DB_HOST=localhost
DB_PORT=5432
SECRET_KEY=genera-una-clave-segura-aqui
DEBUG=False
ALLOWED_HOSTS=tu-dominio.com,127.0.0.1
```

Para generar un `SECRET_KEY` seguro:
```bash
python -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())"
```

---

## Paso 4 — Aplicar migraciones (base de datos vacía)

```bash
python manage.py migrate
```

Esto crea todas las tablas directamente en PostgreSQL con la estructura correcta.

---

## Paso 5 — Usuarios y datos: dos caminos posibles

A partir de aquí hay **dos caminos mutuamente excluyentes**. Elige uno según
tu caso:

- **Opción A — Instalación nueva** (no tienes datos previos en SQLite que
  conservar, solo quieres arrancar limpio en PostgreSQL).
- **Opción B — Migración con datos existentes** (ya tienes productos,
  ventas, compras, usuarios, etc. en SQLite y quieres conservarlos).

---

### Opción A — Instalación nueva (sin datos previos)

```bash
python manage.py createsuperuser
```

Listo. Continúa en el **Paso 7**.

---

### Opción B — Migración con datos existentes desde SQLite

> ⚠️ **No ejecutes `createsuperuser` en esta opción.** El dump que vas a
> cargar ya incluye tus usuarios (incluido el/los administradores
> existentes). Si creas un superusuario nuevo ANTES de cargar el dump,
> `loaddata` lo **sobrescribirá silenciosamente sin avisar** (porque el
> usuario del dump tiene el mismo `id` que el que acabas de crear) y
> perderás esa cuenta sin ningún mensaje de error.

```bash
# 1. Con la BD SQLite activa (sin DB_NAME y sin DJANGO_ENV=production en
#    .env), exportar datos
python manage.py dumpdata \
    --exclude auth.permission \
    --exclude contenttypes \
    --exclude admin.logentry \
    --exclude sessions \
    --indent 2 \
    -o data_backup.json

# 2. Configurar .env completo para PostgreSQL (DB_NAME, DJANGO_ENV=production,
#    y el resto de variables — ver DEPLOY.md, Paso 4)

# 3. Aplicar migraciones en PostgreSQL (base vacía, SIN crear superusuario)
python manage.py migrate

# 4. Cargar los datos (esto crea automáticamente tus usuarios, incluido el admin)
python manage.py loaddata data_backup.json
```

> ⚠️ Si tu `.env` ya tiene `DJANGO_ENV=production` pero todavía le faltan
> variables obligatorias de `settings_prod.py` (ver tabla en `DEPLOY.md`,
> Paso 4), **cualquier** comando `manage.py` fallará con un error tipo
> `UndefinedValueError` — incluido el `dumpdata` del paso 1. Si eso ocurre
> durante el paso 1, simplemente quita (o comenta) `DJANGO_ENV=production`
> de `.env` hasta llegar al paso 2, donde sí debe quedar completo.

**¿Por qué excluir `admin.logentry` y `sessions`?**

- `admin.logentry` (el historial de "quién cambió qué" del panel
  `/django-admin/`) referencia a `contenttypes`, que ya excluimos. Los
  `id` de `contenttypes` se regeneran al hacer `migrate` en la base nueva
  y, aunque en la práctica suelen coincidir si la migración se hace con el
  mismo código, no está garantizado — un desajuste haría que el historial
  apunte al modelo equivocado sin que nada falle visiblemente. Esta tabla
  es solo informativa para el panel de Django y no la usa el sistema, así
  que no vale la pena el riesgo.
- `sessions` son sesiones de navegador activas en el servidor viejo,
  firmadas con el `SECRET_KEY` del servidor viejo. En el servidor nuevo
  (que debe tener un `SECRET_KEY` *distinto*, ver Paso 3) esas sesiones no
  sirven para nada — son basura que ocupa espacio.

Ninguna de las dos tablas contiene información de negocio: productos,
ventas, compras, clientes, cuentas por pagar/cobrar, auditoría del sistema
(`core.auditoriaaccion`), tasas BCV, etc. **sí** se incluyen en el dump y se
migran completas.

**Verificar que todo se cargó correctamente** — compara los conteos antes
y después (en SQLite y en PostgreSQL respectivamente):

```bash
python manage.py shell -c "
from django.apps import apps
for model in apps.get_models():
    label = model._meta.label
    if label.startswith(('core.', 'inventario.', 'compras.', 'ventas.')):
        print(f'{label:35s} {model.objects.count()}')
"
```

Si algún conteo no coincide con el de la base SQLite original, revisa el
log de `loaddata` (suele indicar exactamente qué fixture/objeto falló).

> Si `loaddata` falla por conflictos de claves de todas formas, puedes
> cargar app por app para ubicar el problema:
> ```bash
> python manage.py loaddata data_backup.json --app core
> python manage.py loaddata data_backup.json --app inventario
> python manage.py loaddata data_backup.json --app compras
> python manage.py loaddata data_backup.json --app ventas
> ```

---

## Paso 7 — Colectar estáticos (producción)

```bash
python manage.py collectstatic --noinput
```

---

## Verificación rápida

```bash
# Comprobar conexión y migraciones
python manage.py showmigrations

# Ver qué motor de BD está usando
python manage.py shell -c "
from django.db import connection
print('Motor:', connection.vendor)
print('Base de datos:', connection.settings_dict['NAME'])
"
```

---

## Por qué se agregó `null=True` a tres campos

Los campos `Producto.codigo`, `Venta.numero_factura` y `Compra.numero_referencia`
usan un patrón de dos pasos en `save()`:

1. Se hace el `INSERT` sin código (aún no hay `pk`)
2. Se genera el código con el `pk` asignado y se hace `UPDATE`

En **SQLite** esto funcionaba porque el motor era tolerante con strings vacíos
`''` y la restricción `UNIQUE`. En **PostgreSQL**, dos inserciones concurrentes
con `''` en un campo `UNIQUE NOT NULL` colisionan con `UniqueConstraintError`.

La solución es guardar `NULL` en el primer `INSERT` (los `NULL` no colisionan
con `UNIQUE` en SQL estándar), y luego el `UPDATE` pone el valor real.
