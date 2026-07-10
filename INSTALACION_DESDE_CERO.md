# Instalación completa desde cero — Inversiones Ramón

Esta guía asume que tienes una **laptop nueva con Windows**, en la que:

- **Ya instalaste PostgreSQL** (lo mencionas tú), pero todavía no creaste
  ningún usuario ni base de datos dentro de él — eso lo hacemos aquí.
- **Todavía no tienes** Python, el proyecto, ni nada más instalado.
- No sabes bien cómo funciona una base de datos ni cómo se "pone a correr"
  un sistema en modo producción — está bien, no vamos a asumir nada; cada
  paso explica qué escribir, qué deberías ver, y qué hacer si algo no
  coincide.

Sigue los pasos **en el orden exacto** en que están. No te saltes ninguno
aunque creas que "ya lo hiciste antes" — cada paso indica cómo comprobar
que quedó bien antes de seguir al siguiente.

---

## Índice

1. [Verificar/instalar Python](#paso-1)
2. [Verificar que PostgreSQL quedó bien instalado](#paso-2)
3. [Descomprimir el proyecto](#paso-3)
4. [Crear el entorno virtual e instalar las dependencias](#paso-4)
5. [Crear el usuario y la base de datos en PostgreSQL](#paso-5)
6. [Configurar el archivo `.env`](#paso-6)
7. [Aplicar las migraciones (crear las tablas)](#paso-7)
8. [Crear tu usuario administrador](#paso-8)
9. [Probar el sistema en modo desarrollo](#paso-9)
10. [Modo producción — qué es y cómo activarlo en TU laptop](#paso-10)
11. [Errores comunes y cómo resolverlos](#paso-11)
12. [Resumen para el día a día](#paso-12)

---

<a name="paso-1"></a>
## Paso 1 — Verificar/instalar Python

1. Abre el **Símbolo del sistema**: presiona la tecla de Windows, escribe
   `cmd` y presiona Enter.
2. Escribe exactamente:
   ```
   python --version
   ```
3. **Si responde algo como** `Python 3.11.x` o `Python 3.12.x` (cualquier
   3.10 en adelante sirve): perfecto, salta al Paso 2.

**Si dice "'python' no se reconoce como un comando interno o externo"**,
no tienes Python instalado todavía:

1. Ve a https://www.python.org/downloads/ y haz clic en el botón amarillo
   grande que dice "Download Python 3.x.x".
2. Abre el instalador descargado. **MUY IMPORTANTE**: en la primera
   pantalla, ABAJO DEL TODO, hay una casilla que dice **"Add python.exe to
   PATH"**. Márcala ANTES de hacer clic en "Install Now". Si no la marcas,
   Windows no sabrá dónde está Python y tendrás que reinstalar.
3. Espera a que termine (1-2 minutos) y haz clic en "Close".
4. **Cierra** el Símbolo del sistema que tenías abierto y **ábrelo de
   nuevo** (los cambios de PATH no aplican en ventanas ya abiertas).
5. Repite el paso 2. Ahora sí debe responder con la versión.

---

<a name="paso-2"></a>
## Paso 2 — Verificar que PostgreSQL quedó bien instalado

Como ya instalaste PostgreSQL, aquí solo confirmamos que quedó
correctamente configurado y anotamos un dato clave que necesitarás más
adelante: **la contraseña del usuario `postgres`** (el administrador de
PostgreSQL, no de Windows).

### 2.1 — Confirmar que el servicio está corriendo

1. Presiona la tecla de Windows, escribe `servicios` y abre la app
   **"Servicios"**.
2. Busca en la lista un servicio llamado algo como
   **`postgresql-x64-16`** (el número puede variar según la versión que
   instalaste: 15, 16, 17...).
3. En la columna "Estado" debe decir **"En ejecución"**.
   - Si no dice eso, haz clic derecho sobre él → **Iniciar**.
   - Si no aparece ningún servicio con ese nombre, la instalación de
     PostgreSQL no terminó bien — vuelve a correr el instalador que
     descargaste (de https://www.postgresql.org/download/windows/) y
     complétalo hasta el final; no necesitas desinstalar nada primero.

### 2.2 — Confirmar que pgAdmin abre y recuerdas la contraseña de `postgres`

**pgAdmin 4** es el programa visual para administrar PostgreSQL — viene
incluido automáticamente cuando instalas PostgreSQL en Windows.

1. Presiona la tecla de Windows y escribe `pgAdmin`. Ábrelo (puede tardar
   10-20 segundos la primera vez, es normal — abre dentro de una ventana
   que por dentro funciona como un navegador).
2. La **primera vez** que lo abres, te pedirá crear una **"master
   password"** — es una contraseña propia de pgAdmin (para proteger sus
   ajustes), **distinta** de la contraseña de PostgreSQL. Créala y
   apúntala en algún lugar seguro (una nota, un gestor de contraseñas).
3. En el panel izquierdo ("Browser"), haz doble clic en tu servidor
   (aparece como **"PostgreSQL 16"** o similar). Te va a pedir la
   **contraseña del usuario `postgres`** — es la que escribiste durante
   la instalación de PostgreSQL, en la pantalla que decía "Password for
   the database superuser (postgres)".

   > **¿No recuerdas esa contraseña?** Es la única que no se puede
   > recuperar fácilmente sin reinstalar. Si no la recuerdas con
   > seguridad, lo más simple es desinstalar PostgreSQL (Panel de
   > Control → Programas → PostgreSQL → Desinstalar) y volver a
   > instalarlo desde cero, anotando la contraseña esta vez en un lugar
   > seguro apenas la escribas.

4. Si conectó y ves el árbol expandirse (Databases, Login/Group Roles,
   etc.), quedó confirmado: PostgreSQL funciona y tienes acceso. **Marca
   "Save password"** si te lo ofrece, así no te la vuelve a pedir en esta
   laptop.

Deja pgAdmin abierto — lo vamos a usar de nuevo en el Paso 5.

---

<a name="paso-3"></a>
## Paso 3 — Descomprimir el proyecto

1. Descarga el archivo `inversiones_ramon.zip` que te pasé.
2. Haz clic derecho sobre el zip → **"Extraer todo..."**.
3. Como destino, usa una ruta **corta, sin espacios ni acentos**, por
   ejemplo:
   ```
   C:\inversiones_ramon
   ```
   Crea esa carpeta si Windows no te la ofrece por defecto.
4. **Verificación importante**: al terminar de extraer, abre la carpeta
   `C:\inversiones_ramon` en el Explorador de archivos. Debes ver el
   archivo `manage.py` **directamente** ahí adentro (no dentro de otra
   carpeta llamada `inversiones_ramon` otra vez). Si el extractor creó una
   subcarpeta duplicada, entra a ella y mueve todo su contenido un nivel
   arriba, luego borra la subcarpeta vacía.

---

<a name="paso-4"></a>
## Paso 4 — Crear el entorno virtual e instalar las dependencias

Un **entorno virtual** es una copia aislada de Python solo para este
proyecto, para que sus dependencias (Django, etc.) no se mezclen con
ningún otro programa Python que tengas o instales en el futuro.

1. En el Símbolo del sistema, entra a la carpeta del proyecto:
   ```
   cd C:\inversiones_ramon
   ```
2. Crea el entorno virtual:
   ```
   python -m venv venv
   ```
   Tarda unos segundos y crea una carpeta `venv\` dentro del proyecto.
3. Actívalo:
   ```
   venv\Scripts\activate
   ```
   Si funcionó, la línea de comandos ahora empieza con `(venv)`:
   ```
   (venv) C:\inversiones_ramon>
   ```
   **Cada vez que abras una ventana nueva del Símbolo del sistema para
   trabajar en este proyecto, repite este paso 3** (los pasos 1 y 2 de
   esta sección no hace falta repetirlos nunca más).

   > Si usas **PowerShell** en vez del Símbolo del sistema y te sale un
   > error de "execution policy" al activar, ejecuta primero:
   > ```
   > Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
   > ```
   > y luego `venv\Scripts\Activate.ps1`.

4. Con `(venv)` visible, instala todo lo que necesita el proyecto:
   ```
   pip install -r requirements.txt
   ```
   Descarga e instala Django, el conector de PostgreSQL, etc. Tarda uno o
   dos minutos. Al terminar no debe haber ninguna línea en rojo que diga
   `ERROR`.

   > **Si ves un error mencionando `psycopg2`, `Microsoft Visual C++
   > 14.0` o `Failed building wheel`**: revisa que estés usando el
   > `requirements.txt` de este mismo zip (ya trae fijado
   > `psycopg2-binary`, que no necesita compilar nada en Windows). No
   > necesitas instalar Visual C++ ni ninguna otra herramienta.

---

<a name="paso-5"></a>
## Paso 5 — Crear el usuario y la base de datos en PostgreSQL

Vamos a crear, dentro de PostgreSQL: un **usuario** llamado `ramon_user` y
una **base de datos** llamada `inversiones_ramon`, de la cual ese usuario
es dueño. Piensa en PostgreSQL como un edificio con varios apartamentos
(bases de datos) — aquí construimos el apartamento y le damos las llaves
a su dueño.

1. Vuelve a pgAdmin (o ábrelo si lo cerraste — Paso 2.2).
2. En el panel izquierdo, haz clic derecho sobre tu servidor (el nodo de
   arriba, tipo "PostgreSQL 16") → **Query Tool**. Se abre un editor de
   texto en blanco a la derecha.
3. Pega exactamente esto, cambiando **solo** `tu_password_seguro` por una
   contraseña que inventes tú (apúntala — la necesitarás en el Paso 6):

   ```sql
   CREATE USER ramon_user WITH PASSWORD 'tu_password_seguro';
   CREATE DATABASE inversiones_ramon OWNER ramon_user;
   ```

4. Ejecuta con el botón ▶ (o presiona `F5`).
5. En el panel de mensajes de abajo debe aparecer algo como:
   ```
   Query returned successfully
   ```
   Si en vez de eso dice `role "ramon_user" already exists` o `database
   "inversiones_ramon" already exists`, significa que ya los habías creado
   antes (por ejemplo, si repites esta guía) — no es un error grave, solo
   ejecuta cada línea que SÍ aplique, o continúa al siguiente punto.

### Verificación visual

En el panel izquierdo, clic derecho sobre **Databases** → **Refresh**.
Debe aparecer `inversiones_ramon` en la lista. Si la expandes, estará
vacía por ahora (sin tablas) — es normal, Django las crea en el Paso 7.

---

<a name="paso-6"></a>
## Paso 6 — Configurar el archivo `.env`

Este archivo guarda la configuración **de tu computadora** (contraseñas,
nombre de la base de datos, etc.). Nunca se comparte ni se sube a ningún
lado — por eso el proyecto solo trae `.env.example` como plantilla, y en
tu caso ya viene además un `.env` con valores de ejemplo que debes ajustar
a lo que TÚ creaste en el Paso 5.

1. En el Explorador de Windows, dentro de `C:\inversiones_ramon`, activa
   la vista de "Elementos ocultos" si no ves el archivo `.env` (pestaña
   "Vista" → marca "Elementos ocultos" — los archivos que empiezan con
   punto están ocultos por defecto).
2. Ábrelo con el Bloc de notas. Desde el Símbolo del sistema (con
   `(venv)` activo), lo más simple es:
   ```
   notepad .env
   ```
3. Genera una clave secreta única para tu instalación (copia el
   resultado, lo usarás enseguida):
   ```
   python -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())"
   ```
   Esto imprime una cadena larga de letras y símbolos, distinta cada vez
   que la generas.
4. En el Bloc de notas, edita/completa estas líneas (deja el resto del
   archivo tal cual está):

   ```ini
   SECRET_KEY=PEGA_AQUI_LA_CLAVE_QUE_ACABAS_DE_GENERAR
   DEBUG=True
   ALLOWED_HOSTS=localhost,127.0.0.1

   DB_NAME=inversiones_ramon
   DB_USER=ramon_user
   DB_PASSWORD=la_contraseña_que_pusiste_en_el_paso_5
   DB_HOST=localhost
   DB_PORT=5432
   ```

   - `SECRET_KEY`: pega el valor generado en el punto 3 (sin comillas, sin
     espacios extra).
   - `DB_PASSWORD`: exactamente la contraseña que escribiste en el
     `CREATE USER` del Paso 5.
   - No agregues `DJANGO_ENV=production` todavía — de eso habla el
     Paso 10.
   - Las líneas de `EMAIL_HOST_USER` / `EMAIL_HOST_PASSWORD` y
     `CSRF_TRUSTED_ORIGINS` déjalas comentadas (con `#` delante) por
     ahora.

5. Guarda con `Ctrl+S` y cierra el Bloc de notas.

   > ⚠️ El archivo debe llamarse exactamente `.env` — si el Bloc de notas
   > te ofrece "Guardar como" y agrega `.txt` al final por error, renombra
   > el archivo quitándole esa extensión.

---

<a name="paso-7"></a>
## Paso 7 — Aplicar las migraciones (crear las tablas)

Las "migraciones" son instrucciones que le dicen a Django exactamente qué
tablas y columnas crear en tu base de datos, según los modelos del
sistema (productos, ventas, compras, etc.).

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

**Si aparece un error mencionando** `DB_NAME`, `DB_USER` o `DB_PASSWORD`
(algo como "not found" o `UndefinedValueError`): revisa el Paso 6 — el
`.env` no tiene esa variable o tiene un error de escritura (recuerda:
`CLAVE=valor`, sin espacios alrededor del `=`, sin comillas).

**Si aparece un error de conexión** (`could not connect to server` /
`password authentication failed for user "ramon_user"`): revisa que:
- El servicio de PostgreSQL siga "En ejecución" (Paso 2.1).
- `DB_PASSWORD` en `.env` sea exactamente igual a la que pusiste en el
  `CREATE USER` del Paso 5 (mayúsculas/minúsculas importan).

---

<a name="paso-8"></a>
## Paso 8 — Crear tu usuario administrador

Este sistema usa un modelo de usuario propio (con cédula y rol), así que
no se crea con el comando estándar de Django — se hace con un pequeño
script desde la consola de Python de Django.

Con `(venv)` activo:

```
python manage.py shell
```

Se abre una consola interactiva (verás `>>>`). Pega este bloque completo
**cambiando** el correo, la cédula, la contraseña y tu nombre por los
tuyos reales, y presiona Enter:

```python
from core.models import Usuario
Usuario.objects.create_superuser(
    username='admin',
    email='tu_correo@ejemplo.com',
    password='TuContraseñaSegura123',
    cedula='V-00000000',
    rol='admin',
    first_name='Tu Nombre',
    last_name='Tu Apellido'
)
```

Debe responder mostrando el usuario creado, algo como
`<Usuario: Tu Apellido, Tu Nombre>`. Sal de la consola:

```python
exit()
```

> `rol='admin'` es lo que te da acceso a las secciones administrativas
> (usuarios, reportes, cuentas por pagar/cobrar), más allá de los
> permisos internos de Django.

---

<a name="paso-9"></a>
## Paso 9 — Probar el sistema en modo desarrollo

"Modo desarrollo" es correr el sistema con el servidor rápido y simple
que trae Django (`runserver`) — perfecto para probar, pero **no
recomendado para usarlo todos los días con datos reales del negocio**
sin supervisión (no está pensado para eso; ver Paso 10).

Con `(venv)` activo:

```
python manage.py runserver
```

Deberías ver:
```
Watching for file changes with StatReloader
...
Django version 4.2.x, using settings 'inversiones_ramon.settings'
Starting development server at http://127.0.0.1:8000/
Quit the server with CTRL-BREAK.
```

Abre tu navegador y entra a:

```
http://127.0.0.1:8000/
```

Debe aparecer la pantalla de **login**. Entra con el usuario y contraseña
que creaste en el Paso 8. Si todo funciona, llegarás al panel principal.

Para **detener** el servidor: en la ventana del Símbolo del sistema,
presiona `Ctrl+C`.

Si esta prueba funciona, tu instalación está completa y correcta. El
Paso 10 es opcional/complementario — léelo cuando quieras usar el sistema
de forma más estable en el día a día.

---

<a name="paso-10"></a>
## Paso 10 — Modo producción: qué es y cómo activarlo en TU laptop

Aquí es donde más se suele confundir la gente, así que vamos despacio.

### 10.1 — ¿Qué significa "producción" realmente?

"Producción" no es un botón mágico — es simplemente **un conjunto de
configuraciones distintas** que se activan cuando el sistema va a ser
usado de verdad (con datos reales, todos los días) en vez de solo estar
probándolo. Las diferencias principales son:

| | Desarrollo (`runserver`) | Producción |
|---|---|---|
| `DEBUG` | `True` — si algo falla, muestra el error técnico completo en pantalla (útil para programar, **peligroso** si lo ve un cliente o alguien ajeno) | `False` — si algo falla, muestra una pantalla genérica de error, sin detalles internos |
| Servidor | `runserver` — hecho para pruebas, se recarga solo al guardar cambios, pero no está optimizado para manejar varias personas usando el sistema a la vez de forma estable por horas | Un servidor real (gunicorn, waitress) — pensado para correr sin caerse durante todo el día |
| Archivos estáticos (CSS/imágenes) | Los sirve Django directamente, de forma simple | Los sirve un sistema optimizado (WhiteNoise) |

### 10.2 — Tu caso específico: ¿tu laptop o un servidor con dominio?

Este proyecto trae **dos escenarios de producción completamente
distintos**, y es importante que sepas cuál te corresponde:

**Escenario A — "Producción casera": el sistema corre solo en tu propia
laptop**, tú (u otra persona en la misma laptop) lo usa localmente, sin
necesidad de que nadie fuera de esa computadora entre por internet.

**Escenario B — Producción real con servidor**: quieres que el sistema
esté disponible en un dominio de internet (por ejemplo
`www.inversionesramon.com`), accesible desde cualquier computadora o
celular, funcionando 24 horas al día en un servidor dedicado (no tu
laptop personal). Esto requiere un **servidor Linux contratado** (una
VPS, por ejemplo en DigitalOcean, Hetzner, AWS, etc.) — **no se puede
hacer con Windows ni con tu laptop personal** de forma confiable, porque
necesita estar encendida siempre, con una IP fija y configuración de
seguridad avanzada.

Si tu plan es el **Escenario B**, ese es exactamente el propósito del
archivo **`DEPLOY.md`** que viene incluido en este proyecto — sigue esa
guía completa cuando tengas contratado el servidor Linux y el dominio.
No la necesitas ahora si solo vas a usar el sistema en tu laptop.

A continuación cubrimos el **Escenario A**, que es probablemente tu caso
inmediato: quieres algo más estable que `runserver` para usar a diario en
tu propia laptop, sin montar todo un servidor Linux.

### 10.3 — Escenario A paso a paso: correr el sistema de forma más estable en tu laptop

`runserver` funciona, pero no es lo ideal para dejarlo corriendo todo el
día. En Windows, el equivalente sencillo a "gunicorn" (que usa
`DEPLOY.md`, pero que **no funciona en Windows**) es **Waitress** — un
servidor de producción escrito en Python puro, sin necesidad de
configuración adicional ni de Linux.

1. Con `(venv)` activo, instala Waitress:
   ```
   pip install waitress
   ```

2. Edita tu `.env` (Paso 6) y cambia esta línea:
   ```ini
   DEBUG=False
   ```
   Deja todo lo demás igual. **No** agregues `DJANGO_ENV=production` en
   este escenario — eso activaría `settings_prod.py`, que **fuerza
   HTTPS** (pensado para el Escenario B, con Nginx y certificado SSL). En
   tu laptop, sin ese proxy, forzar HTTPS haría que el sistema no cargue
   en el navegador. Con solo `DEBUG=False` ya ocultas los errores
   técnicos internos, que es la parte que más importa para uso diario.

3. Reúne los archivos estáticos (CSS, imágenes) en una sola carpeta lista
   para servir eficientemente:
   ```
   python manage.py collectstatic --noinput
   ```
   Esto crea una carpeta `staticfiles\` — es normal y es necesaria con
   `DEBUG=False`.

4. Corre el sistema con Waitress en vez de `runserver`:
   ```
   waitress-serve --port=8000 inversiones_ramon.wsgi:application
   ```
   Deberías ver algo como:
   ```
   INFO:waitress:Serving on http://0.0.0.0:8000
   ```
   Entra en el navegador a `http://127.0.0.1:8000/` — debe funcionar
   igual que con `runserver`, pero ahora corriendo con un servidor
   pensado para uso continuo.

   Para detenerlo: `Ctrl+C` en esa ventana.

5. **(Opcional) Acceder desde otro dispositivo en la misma red Wi-Fi**
   (por ejemplo, un celular o tablet en la misma casa/negocio): en vez de
   `127.0.0.1`, usa la IP local de tu laptop. Para verla:
   ```
   ipconfig
   ```
   busca "Dirección IPv4" (algo como `192.168.1.105`). Desde el otro
   dispositivo, en la misma red Wi-Fi, entra a `http://192.168.1.105:8000/`.
   Para que esto funcione también debes agregar esa IP a `.env`:
   ```ini
   ALLOWED_HOSTS=localhost,127.0.0.1,192.168.1.105
   ```
   y reiniciar Waitress. Ten en cuenta que esto **solo funciona dentro de
   la misma red Wi-Fi/local** — no es acceso por internet real (para eso
   sí necesitas el Escenario B con un servidor y dominio).

6. **Volver a modo desarrollo cuando lo necesites** (por ejemplo, para
   que te muestre errores detallados si algo falla): simplemente vuelve
   a poner `DEBUG=True` en `.env` y usa `python manage.py runserver` en
   vez de `waitress-serve`.

> Waitress no se queda corriendo solo si cierras la ventana o apagas la
> laptop — cada vez que quieras usar el sistema en este modo, repites el
> comando del punto 4. Automatizar que arranque solo con Windows (como un
> servicio) es posible pero es un paso más avanzado — dilo si en algún
> momento lo necesitas y lo vemos.

---

<a name="paso-11"></a>
## Paso 11 — Errores comunes y cómo resolverlos

| Síntoma | Causa más probable | Solución |
|---|---|---|
| `'python' no se reconoce como un comando` | Python no está en el PATH | Reinstalar marcando "Add python.exe to PATH" (Paso 1) |
| `password authentication failed for user "ramon_user"` | `.env` tiene una contraseña distinta a la del `CREATE USER` | Revisar Paso 5 y 6 — deben coincidir exactamente |
| `could not connect to server: Connection refused` | El servicio de PostgreSQL no está corriendo | Abrir "Servicios" en Windows y arrancarlo (Paso 2.1) |
| `UndefinedValueError: DB_NAME not found` | Falta una variable en `.env`, o el archivo no se llama exactamente `.env` | Revisar Paso 6, incluyendo que no sea `.env.txt` |
| Error de `psycopg2` / `Visual C++ 14.0` al instalar | `requirements.txt` desactualizado o corrupto | Usar el de este zip (ya corregido) y repetir `pip install -r requirements.txt` |
| La página carga en blanco o da error 400 con `DEBUG=False` | Falta agregar tu host/IP a `ALLOWED_HOSTS` | Revisar Paso 10.3, punto 5 |
| Al activar el venv en PowerShell, error de "execution policy" | Restricción de seguridad de PowerShell | `Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass` y reintentar |

---

<a name="paso-12"></a>
## Paso 12 — Resumen para el día a día

Una vez que ya pasaste por todos los pasos anteriores una vez, **para
volver a usar el sistema normalmente solo necesitas**:

**Modo desarrollo/pruebas:**
```
cd C:\inversiones_ramon
venv\Scripts\activate
python manage.py runserver
```
y abrir `http://127.0.0.1:8000/`.

**Modo producción casera (recomendado para uso diario real):**
```
cd C:\inversiones_ramon
venv\Scripts\activate
waitress-serve --port=8000 inversiones_ramon.wsgi:application
```
y abrir `http://127.0.0.1:8000/`.

Ya no necesitas repetir los pasos 1 a 8 — esos son de instalación
inicial, se hacen una sola vez por laptop. El servicio de PostgreSQL
normalmente arranca solo junto con Windows, así que tampoco tienes que
iniciarlo manualmente cada vez (solo revisa el Paso 2.1 si algo falla).

---

## ¿Y `MIGRACION_POSTGRESQL.md` y `DEPLOY.md`?

- **`MIGRACION_POSTGRESQL.md`** te sirve únicamente si en el futuro
  tienes **otra base de datos vieja** (por ejemplo, un `db.sqlite3` con
  datos reales de una instalación anterior) y quieres traer esos datos a
  esta base nueva en PostgreSQL. Si instalaste todo desde cero como en
  esta guía, no la necesitas.

- **`DEPLOY.md`** es para el **Escenario B** del Paso 10: el día que
  decidas contratar un servidor Linux con dominio propio para que el
  sistema esté disponible por internet, 24/7, para varias personas desde
  cualquier lugar. Mientras lo uses en tu laptop (Escenario A), no lo
  necesitas.
