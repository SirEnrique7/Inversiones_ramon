# Guía paso a paso — Correr el sistema en Windows con PostgreSQL

Esta guía asume:
- Windows.
- PostgreSQL ya instalado (con pgAdmin 4, que viene incluido en el
  instalador de PostgreSQL para Windows).
- El proyecto va a correr **solo en tu laptop**, para desarrollo —
  por eso aquí NO se usa `DJANGO_ENV=production` ni nada de
  `DEPLOY.md`. Al final explico cuándo te van a servir
  `MIGRACION_POSTGRESQL.md` y `DEPLOY.md`.

Sigue los pasos **en orden**. Cada uno indica exactamente qué escribir y
qué deberías ver.

---

## Paso 1 — Verificar que tienes Python instalado

1. Abre el **Símbolo del sistema** (búscalo en el menú de Windows como
   "cmd" o "Símbolo del sistema").
2. Escribe:
   ```
   python --version
   ```
3. Debe responder algo como `Python 3.11.x` o `Python 3.12.x` (cualquier
   versión 3.10 o superior sirve).

**Si dice "no se reconoce como un comando"**: no tienes Python instalado
o no quedó en el PATH.
- Descárgalo de https://www.python.org/downloads/ (botón amarillo
  "Download Python 3.x.x").
- Al instalar, en la PRIMERA pantalla del instalador, marca la casilla
  **"Add python.exe to PATH"** (abajo del todo) ANTES de darle a "Install
  Now". Esto es importante — si no la marcas, tendrás el mismo problema.
- Cierra y vuelve a abrir el Símbolo del sistema, y repite el paso 2.

---

## Paso 2 — Descomprimir el proyecto

1. Descarga el archivo `proyecto_corregido.zip` que te pasé.
2. Haz clic derecho sobre el zip → **"Extraer todo..."**.
3. Como destino, usa una ruta **corta y sin espacios ni acentos**, por
   ejemplo:
   ```
   C:\inversiones_ramon
   ```
   (Crea esa carpeta si no existe — al extraer, asegúrate de que el
   contenido quede directamente en `C:\inversiones_ramon\` y no en
   `C:\inversiones_ramon\proyecto_corregido\`. Si el extractor crea una
   subcarpeta extra, mueve todo el contenido un nivel arriba.)
4. Para comprobarlo: dentro de `C:\inversiones_ramon` debes ver, entre
   otras cosas, el archivo `manage.py` directamente (no dentro de otra
   carpeta).

---

## Paso 3 — Crear el entorno virtual e instalar las dependencias

1. En el Símbolo del sistema, entra a la carpeta del proyecto:
   ```
   cd C:\inversiones_ramon
   ```
2. Crea el entorno virtual (una copia aislada de Python solo para este
   proyecto):
   ```
   python -m venv venv
   ```
   Esto crea una carpeta `venv\` dentro del proyecto. Tarda unos segundos.
3. Activa el entorno virtual:
   ```
   venv\Scripts\activate
   ```
   Si todo va bien, la línea de comandos ahora empieza con `(venv)`, por
   ejemplo:
   ```
   (venv) C:\inversiones_ramon>
   ```
   **Cada vez que abras una ventana nueva del Símbolo del sistema para
   trabajar en este proyecto, tendrás que repetir este paso 3 (activar el
   entorno)** — los pasos 1-2 no hace falta repetirlos.

   > Si usas **PowerShell** en vez del Símbolo del sistema y al activar
   > te sale un error de "execution policy", ejecuta primero:
   > ```
   > Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
   > ```
   > y luego `venv\Scripts\Activate.ps1`.

4. Con el entorno activado (`(venv)` visible), instala todo lo que
   necesita el proyecto:
   ```
   pip install -r requirements.txt
   ```
   Esto descarga e instala Django, el conector de PostgreSQL, etc. Tarda
   uno o dos minutos. Al final debe terminar sin líneas en rojo que digan
   "ERROR".

   > **Si ves un error mencionando `psycopg2`, `Microsoft Visual C++ 14.0`
   > o `Failed building wheel`**: asegúrate de estar usando la versión de
   > `requirements.txt` incluida en este zip (ya corregido — fija
   > `psycopg2-binary==2.9.12`, que sí trae instalador listo para Windows
   > sin necesidad de compilar nada). Si extrajiste una copia anterior del
   > proyecto, vuelve a extraer este zip y repite el `pip install`. No
   > necesitas instalar Visual C++ ni nada adicional.

---

## Paso 4 — Crear la base de datos en PostgreSQL

Vamos a crear: un **usuario** de PostgreSQL llamado `ramon_user` y una
**base de datos** llamada `inversiones_ramon`, propiedad de ese usuario.

### Opción recomendada — con pgAdmin (visual)

1. Abre **pgAdmin 4** (menú de Windows → carpeta "PostgreSQL 16" →
   "pgAdmin 4"). Se abre en una ventana que internamente es un navegador.
2. Si te pide una "master password", es la que creaste la primera vez que
   abriste pgAdmin (no la de PostgreSQL). Si no la recuerdas, este es un
   programa nuevo para ti — créala y anótala en algún lugar seguro.
3. En el panel izquierdo ("Browser"), haz clic en **Servers** → tu
   servidor (algo como "PostgreSQL 16"). Te pedirá la contraseña del
   usuario `postgres` — es la que pusiste **al instalar PostgreSQL**.
   Marca "Save password" si quieres que no te la vuelva a pedir.
4. Una vez conectado, verás un árbol: Servers → PostgreSQL 16 →
   Databases, Login/Group Roles, etc.
5. Haz clic derecho sobre tu servidor (el nodo "PostgreSQL 16", el de más
   arriba) → **Query Tool**. Se abre un editor de texto en blanco.
6. Pega exactamente esto, cambiando solo `tu_password_seguro` por una
   contraseña que tú elijas (apúntala, la necesitarás en el Paso 5):

   ```sql
   CREATE USER ramon_user WITH PASSWORD 'tu_password_seguro';
   CREATE DATABASE inversiones_ramon OWNER ramon_user;
   ```

7. Ejecuta con el botón ▶ (Execute/Play) o la tecla `F5`.
8. Abajo, en el panel de mensajes, debe decir algo como:
   ```
   Query returned successfully
   ```

### Cómo verificar visualmente que se creó

En el panel izquierdo, haz clic derecho sobre **Databases** → **Refresh**.
Debe aparecer `inversiones_ramon` en la lista. Si la expandes, por ahora
estará vacía (sin tablas) — eso es normal, las tablas las crea Django en
el Paso 6.

---

## Paso 5 — Crear el archivo `.env`

Este archivo guarda la configuración de TU computadora (contraseñas,
nombre de la base de datos, etc.) y **nunca viene incluido en el
proyecto** — cada quien crea el suyo. Por eso solo existe
`.env.example` (una plantilla de ejemplo).

1. En el Símbolo del sistema (con `(venv)` activo, dentro de
   `C:\inversiones_ramon`), copia la plantilla:
   ```
   copy .env.example .env
   ```
2. Genera una clave secreta única para tu proyecto:
   ```
   python -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())"  3hy0r-t$e73v%&b4f@6@0shi@*dwr11-vdje%#7%yepi608
   ```
   Esto imprime una cadena larga de letras y símbolos, por ejemplo:
   ```
   k3$j8d-w2m9... (la tuya será distinta)
   ```
   **Copia ese valor**, lo vas a usar ahora.
3. Abre el archivo `.env` con el Bloc de notas:
   ```
   notepad .env
   ```
4. Verás varias secciones con comentarios (líneas que empiezan con `#`).
   Edita / completa estas líneas (deja el resto del archivo tal cual
   está):

   ```ini
   SECRET_KEY=PEGA_AQUI_LA_CLAVE_QUE_GENERASTE_EN_EL_PASO_ANTERIOR
   DEBUG=True
   ALLOWED_HOSTS=localhost,127.0.0.1

   DB_NAME=inversiones_ramon
   DB_USER=ramon_user
   DB_PASSWORD=tu_password_seguro
   DB_HOST=localhost
   DB_PORT=5432
   ```

   - `SECRET_KEY`: pega el valor del paso 2 (sin comillas, sin espacios).
   - `DB_PASSWORD`: la contraseña que escribiste en el `CREATE USER` del
     Paso 4.
   - **No** agregues `DJANGO_ENV=production` — eso es solo para cuando el
     sistema esté en un servidor real (ver nota final de esta guía).
   - Las líneas de `EMAIL_HOST_USER` / `EMAIL_HOST_PASSWORD` y
     `CSRF_TRUSTED_ORIGINS` puedes dejarlas comentadas (con `#` delante)
     por ahora — solo son obligatorias si activas `DJANGO_ENV=production`.

5. Guarda con `Ctrl+S` y cierra el Bloc de notas.

   > ⚠️ **Importante**: el archivo debe llamarse exactamente `.env` (con
   > el punto al inicio, sin nada más). Como ya lo creaste con `copy` en
   > el paso 1, el Bloc de notas lo abrirá y guardará con ese mismo nombre
   > correctamente — no uses "Guardar como" o podrías terminar con
   > `.env.txt` por error.

---

## Paso 6 — Aplicar las migraciones (crear las tablas en PostgreSQL)

Con `(venv)` activo, dentro de `C:\inversiones_ramon`:

```
python manage.py migrate
```

Deberías ver muchas líneas terminando en `... OK`, por ejemplo:
```
Applying core.0001_initial... OK
Applying core.0002_initial... OK
...
Applying ventas.0002_venta_numero_factura_null... OK
```

Si en cambio aparece un error mencionando `DB_NAME`, `DB_USER` o
`DB_PASSWORD` ("not found" o "UndefinedValueError"), revisa el Paso 5 —
significa que el archivo `.env` no tiene esa variable o tiene un error de
escritura (recuerda: `CLAVE=valor`, sin espacios alrededor del `=`).

Si aparece un error de conexión (`could not connect to server` /
`password authentication failed`), revisa que:
- El servicio de PostgreSQL esté corriendo (en Windows, "Servicios" →
  busca algo como "postgresql-x64-16" → debe estar "En ejecución").
- `DB_PASSWORD` en `.env` sea exactamente la que pusiste en el `CREATE
  USER` del Paso 4.

---

## Paso 7 — Crear tu usuario administrador

Este sistema usa un modelo de usuario propio (con cédula y rol), así que
no se crea con el comando estándar de Django sino con un pequeño script.
Con `(venv)` activo:

```
python manage.py shell
```

Esto abre una consola interactiva de Python (verás `>>>`). Pega este
bloque completo (cambia el correo, la cédula, la contraseña y tu nombre
por los tuyos) y presiona Enter:

```python
from core.models import Usuario
Usuario.objects.create_superuser(
    username='admin',
    email='ramonvaldez2119@gmail.com',
    password='SJEnrique18',
    cedula='V-28678546',
    rol='admin',
    first_name='Jesus',
    last_name='Bolivar'
)
```

Debe responder mostrando el usuario creado, algo como
`<Usuario: Tu Apellido, Tu Nombre>`. Luego sal de la consola:

```python
exit()
```

> `rol='admin'` es importante — es lo que te da acceso a las secciones
> administrativas del sistema (usuarios, reportes financieros, cuentas
> por pagar/cobrar, etc.), independientemente de los permisos internos de
> Django.

---

## Paso 8 — Correr el sistema y verlo en el navegador

Con `(venv)` activo:

```
python manage.py runserver
```

Deberías ver algo como:
```
Watching for file changes with StatReloader
...
Django version 4.2.x, using settings 'inversiones_ramon.settings'
Starting development server at http://127.0.0.1:8000/
Quit the server with CTRL-BREAK.
```

Abre tu navegador (Chrome, Edge, etc.) y entra a:

```
http://127.0.0.1:8000/
```

Deberías ver la pantalla de **login**. Entra con el usuario y contraseña
que creaste en el Paso 7. Si todo funciona, llegarás al panel principal
del sistema.

Para **detener** el servidor: vuelve a la ventana del Símbolo del sistema
y presiona `Ctrl+C` (o `Ctrl+Break`).

---

## Paso 9 (opcional) — Confirmar visualmente que los datos están en PostgreSQL

1. Dentro del sistema (en el navegador), crea algo de prueba — por
   ejemplo, una categoría de producto.
2. Ve a pgAdmin → expande `Databases` → `inversiones_ramon` → `Schemas` →
   `public` → `Tables`. Busca la tabla `inventario_categoria`.
3. Haz clic derecho sobre ella → **View/Edit Data** → **All Rows**.
4. Deberías ver la fila que acabas de crear desde el navegador — esa es
   la confirmación de que el sistema está escribiendo en tu PostgreSQL.

---

## Resumen rápido — para las próximas veces

Cada vez que quieras volver a correr el sistema, **solo necesitas**:

1. Asegúrate de que el servicio de PostgreSQL esté corriendo (normalmente
   arranca solo con Windows).
2. Abre el Símbolo del sistema.
3. ```
   cd C:\inversiones_ramon
   venv\Scripts\activate
   python manage.py runserver
   ```
4. Abre `http://127.0.0.1:8000/` en el navegador.

Ya no necesitas repetir los pasos 1, 2, 4, 5, 6 ni 7 — esos son de
instalación/configuración inicial, se hacen una sola vez.

---

## ¿Y `MIGRACION_POSTGRESQL.md` y `DEPLOY.md`, cuándo los uso?

Con esta guía ya hiciste, en esencia, la **"Opción A — Instalación
nueva"** de `MIGRACION_POSTGRESQL.md` (Paso 5), adaptada a Windows con más
detalle.

- **`MIGRACION_POSTGRESQL.md` → "Opción B"** te servirá únicamente si en
  el futuro tienes **otra base de datos vieja** (por ejemplo, un
  `db.sqlite3` con datos reales de un sistema anterior) y quieres traer
  esos datos a esta base nueva en PostgreSQL. Si empezaste desde cero
  como en esta guía, no la necesitas.

- **`DEPLOY.md`** te servirá el día que decidas que **otras personas
  (no solo tú, en tu laptop)** necesiten acceder al sistema — es decir,
  cuando lo subas a un servidor real con su propio dominio, HTTPS, etc.
  Mientras lo uses solo en tu laptop con `python manage.py runserver`,
  no necesitas nada de ese documento.
