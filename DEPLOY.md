# Guía de Despliegue a Producción

Esta guía asume un servidor Linux (Ubuntu/Debian) limpio, con acceso por
SSH y un dominio ya apuntando a la IP del servidor. Sigue los pasos en
orden — cada uno depende del anterior.

Para la parte de base de datos y migración de datos existentes, esta guía
se apoya en **`MIGRACION_POSTGRESQL.md`**; aquí nos enfocamos en todo lo
que rodea a esa migración: servidor, proceso de la aplicación, proxy con
HTTPS, respaldos y verificación final.

---

## Checklist resumido

- [ ] 1. Paquetes del sistema (Python, PostgreSQL, Nginx)
- [ ] 2. Base de datos PostgreSQL (ver `MIGRACION_POSTGRESQL.md`, Pasos 1-2)
- [ ] 3. Código del proyecto + entorno virtual + dependencias
- [ ] 4. `.env` de producción completo, con permisos `600`
- [ ] 5. Migraciones y datos (ver `MIGRACION_POSTGRESQL.md`, Pasos 4-5)
- [ ] 6. Activar `settings_prod` (la pieza que enciende toda la seguridad)
- [ ] 7. Archivos estáticos (`collectstatic`)
- [ ] 8. gunicorn como servicio (systemd)
- [ ] 9. Nginx como proxy inverso con HTTPS
- [ ] 10. Verificación final
- [ ] 11. Respaldos automáticos de la base de datos
- [ ] 12. Firewall básico

---

## 1. Paquetes del sistema

```bash
sudo apt update
sudo apt install -y python3 python3-venv python3-pip \
                     postgresql postgresql-contrib \
                     nginx git
```

---

## 2. Base de datos PostgreSQL

Sigue **`MIGRACION_POSTGRESQL.md`, Paso 2** para crear el usuario y la base
de datos. No la repetimos aquí para no tener dos fuentes de verdad.

---

## 3. Código del proyecto y entorno virtual

```bash
# Como usuario de despliegue (no root), por ejemplo en /opt/inversiones_ramon
cd /opt
sudo mkdir inversiones_ramon && sudo chown $USER:$USER inversiones_ramon
cd inversiones_ramon

# Copia aquí el contenido del proyecto (git clone, scp, rsync, etc.)

python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

> A partir de aquí, todos los comandos `python manage.py ...` de esta guía
> asumen el entorno virtual activado (`source venv/bin/activate`).

---

## 4. `.env` de producción

```bash
cp .env.example .env
nano .env   # o el editor que prefieras
```

Completa **todas** estas variables. Las marcadas como *obligatoria* no
tienen valor por defecto: si falta alguna, `settings_prod.py` falla al
arrancar (es intencional — mejor que falle al desplegar que en silencio).

| Variable | Obligatoria | Notas |
|---|---|---|
| `DJANGO_ENV` | Sí | Debe ser exactamente `production` — activa `settings_prod.py` (ver Paso 6) |
| `SECRET_KEY` | Sí | Generar una **nueva**, no reutilizar la de desarrollo (ver comando abajo) |
| `ALLOWED_HOSTS` | Sí | Dominio(s) reales, sin `https://`. Ej: `inversionesramon.com,www.inversionesramon.com` |
| `CSRF_TRUSTED_ORIGINS` | Sí | Igual que arriba pero CON `https://`. Ej: `https://inversionesramon.com,https://www.inversionesramon.com` |
| `BEHIND_PROXY` | No (default `True`) | Dejar en `True` — Nginx queda delante de gunicorn (Paso 9) |
| `DB_NAME`, `DB_USER`, `DB_PASSWORD`, `DB_HOST`, `DB_PORT` | Sí | Credenciales de PostgreSQL del Paso 2 |
| `DB_CONN_MAX_AGE` | No (default `60`) | Segundos que se reutiliza cada conexión a la BD |
| `EMAIL_HOST_USER` | Sí | Cuenta SMTP para enviar correos (recuperación de contraseña, etc.) |
| `EMAIL_HOST_PASSWORD` | Sí | Contraseña/clave de aplicación de esa cuenta SMTP |
| `EMAIL_HOST`, `EMAIL_PORT`, `EMAIL_USE_TLS` | No | Por defecto `smtp.gmail.com`, `587`, `True` — cambiar si usas otro proveedor |
| `DEFAULT_FROM_EMAIL` | No | Remitente que verán los usuarios |

Generar un `SECRET_KEY` seguro:

```bash
python -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())"
```

### Permisos del archivo `.env` — no dejarlo legible por cualquiera

Este archivo contiene la contraseña de PostgreSQL, la `SECRET_KEY` y la
contraseña de aplicación del correo SMTP. Si se sube al servidor con los
permisos por defecto de una transferencia normal (`644`), **cualquier
usuario del sistema** con una cuenta en ese servidor puede leerlo con un
simple `cat .env` — no hace falta ser root. En un VPS compartido o con
varios desarrolladores/usuarios, esto es una fuga de credenciales real.

```bash
# Restringir lectura y escritura SOLO al usuario que ejecuta gunicorn
sudo chown www-data:www-data /opt/inversiones_ramon/.env
sudo chmod 600 /opt/inversiones_ramon/.env

# Verificar: debe mostrar "-rw-------" y el dueño correcto
ls -l /opt/inversiones_ramon/.env
```

`600` significa: solo el dueño del archivo puede leerlo y escribirlo —
nadie más, ni siquiera otros usuarios del grupo. Como el servicio de
gunicorn corre como `www-data` (ver Paso 8), ese es el único usuario que
necesita acceso a este archivo.

> ⚠️ Verifica también que `.env` esté en tu `.gitignore` **antes** de
> subir el proyecto a cualquier repositorio, propio o de terceros. Si ya
> se subió por error alguna vez, cambia todas las credenciales que
> contenía — no basta con borrarlo del último commit, sigue existiendo
> en el historial de Git.

---

## 5. Migraciones y carga de datos

Sigue **`MIGRACION_POSTGRESQL.md`**:

- **Paso 4** (`python manage.py migrate`) — crea las tablas.
- **Paso 5** — elige **Opción A** (instalación nueva, `createsuperuser`) o
  **Opción B** (migrar datos existentes desde SQLite con `loaddata`),
  según tu caso. No mezcles ambas (la guía explica por qué).

---

## 6. Activar `settings_prod`

Añade esta línea a tu `.env`:

```
DJANGO_ENV=production
```

Con esto, `manage.py`, `wsgi.py` y `asgi.py` detectan automáticamente que
están en producción y cargan `inversiones_ramon.settings_prod` — activando
HTTPS forzado, cookies seguras, `CSRF_TRUSTED_ORIGINS`, logging a archivo,
etc. **No necesitas configurar nada adicional en systemd** para esto; basta
con que `.env` esté presente y completo (ver tabla del Paso 4).

Verifica que quedó activo:

```bash
python manage.py check --deploy
```

Si esto da `0 issues` (y `.env` tiene todas las variables obligatorias de
la tabla del Paso 4), `settings_prod.py` está funcionando correctamente.

> **Uso avanzado:** si por alguna razón necesitas forzar un módulo de
> settings distinto sin depender de `.env`, puedes seguir definiendo
> `DJANGO_SETTINGS_MODULE` como variable de entorno explícita — tiene
> prioridad sobre `DJANGO_ENV` y se respeta tal cual.

---

## 7. Archivos estáticos

```bash
python manage.py collectstatic --noinput
```

Esto junta CSS/JS/imágenes en `staticfiles/`, que WhiteNoise sirve
directamente desde la aplicación — no necesitas configurar nada adicional
en Nginx para esto.

---

## 8. gunicorn como servicio (systemd)

Crear `/etc/systemd/system/inversiones_ramon.service`:

```ini
[Unit]
Description=Gunicorn — Inversiones Ramón
After=network.target postgresql.service

[Service]
User=www-data
Group=www-data
WorkingDirectory=/opt/inversiones_ramon
EnvironmentFile=/opt/inversiones_ramon/.env
ExecStart=/opt/inversiones_ramon/venv/bin/gunicorn \
          --workers 3 \
          --timeout 60 \
          --bind unix:/run/inversiones_ramon.sock \
          inversiones_ramon.wsgi:application

Restart=on-failure

[Install]
WantedBy=multi-user.target
```

> `EnvironmentFile=.env` hace que systemd exporte cada línea de `.env`
> como variable de entorno real del proceso — incluyendo `DJANGO_ENV=production`,
> que es lo que activa `settings_prod.py` (Paso 6). Asegúrate de que `.env`
> **no** tenga espacios alrededor del `=` (formato `CLAVE=valor`, igual que
> `.env.example`).

> `--timeout 60`: gunicorn mata y reinicia cualquier worker que tarde más
> de este valor en responder (el default es 30s). Los reportes de
> ventas/compras/margen pueden tardar más de 30 segundos una vez que el
> negocio acumule varios años de historial — sin este ajuste, ese reporte
> se cortaría a la mitad con un error 502 justo cuando más datos tenga
> para mostrar. 60s da margen sin dejar workers colgados indefinidamente
> ante un problema real (por ejemplo, la base de datos caída).

Ajusta `User`/`Group`/rutas según tu servidor, y asegúrate de que ese
usuario sea **dueño** de `/opt/inversiones_ramon` (para poder escribir en
`logs/` y `staticfiles/`).

```bash
sudo chown -R www-data:www-data /opt/inversiones_ramon
sudo systemctl daemon-reload
sudo systemctl enable --now inversiones_ramon
sudo systemctl status inversiones_ramon
```

---

## 9. Nginx como proxy inverso con HTTPS

Configuración mínima en `/etc/nginx/sites-available/inversiones_ramon`:

```nginx
server {
    listen 80;
    server_name inversionesramon.com www.inversionesramon.com;

    location / {
        proxy_pass http://unix:/run/inversiones_ramon.sock;
        proxy_set_header Host              $host;
        proxy_set_header X-Real-IP         $remote_addr;
        proxy_set_header X-Forwarded-For   $proxy_add_x_forwarded_for;

        # ⚠️ IMPRESCINDIBLE: settings_prod.py (BEHIND_PROXY=True) confía
        # en este encabezado para saber que la conexión original es HTTPS.
        # Sin esto, SECURE_SSL_REDIRECT=True provoca un loop infinito de
        # redirecciones.
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

```bash
sudo ln -s /etc/nginx/sites-available/inversiones_ramon /etc/nginx/sites-enabled/
sudo nginx -t
sudo systemctl reload nginx
```

Ahora activa HTTPS con Let's Encrypt (certbot reescribe el bloque anterior
para añadir `listen 443 ssl;` y redirigir el puerto 80 a 443
automáticamente, conservando el `proxy_set_header X-Forwarded-Proto
$scheme;` que ya pusiste):

```bash
sudo apt install -y certbot python3-certbot-nginx
sudo certbot --nginx -d inversionesramon.com -d www.inversionesramon.com
```

---

## 10. Verificación final

```bash
# 1. Chequeo de despliegue de Django (debe dar "0 issues")
python manage.py check --deploy

# 2. El sitio responde y redirige a HTTPS
curl -I http://inversionesramon.com    # debe responder 301 -> https://...
curl -I https://inversionesramon.com   # debe responder 200

# 3. Revisar logs en vivo mientras navegas un poco
sudo journalctl -u inversiones_ramon -f
tail -f /opt/inversiones_ramon/logs/errores.log
```

Con el navegador:

1. Entra al dominio por HTTPS y haz login con el usuario administrador.
2. Crea un producto, una venta y una orden de compra de prueba — confirma
   que todo el flujo funciona igual que en tus pruebas locales.
3. Prueba "Olvidé mi contraseña" y confirma que llega el correo (valida
   `EMAIL_HOST_USER`/`EMAIL_HOST_PASSWORD`).

---

## 11. Respaldos automáticos de PostgreSQL

Crear `/opt/inversiones_ramon/backup_db.sh`:

```bash
#!/bin/bash
set -e
FECHA=$(date +%Y%m%d_%H%M%S)
DESTINO=/opt/inversiones_ramon/backups
mkdir -p "$DESTINO"

PGPASSWORD='tu_password_seguro' pg_dump \
    -h localhost -U ramon_user -d inversiones_ramon \
    -F c -f "$DESTINO/inversiones_ramon_$FECHA.dump"

# Conservar solo los últimos 14 respaldos
ls -1t "$DESTINO"/inversiones_ramon_*.dump | tail -n +15 | xargs -r rm --
```

```bash
chmod +x /opt/inversiones_ramon/backup_db.sh
```

Programar con cron (respaldo diario a las 2:00 a.m.):

```bash
crontab -e
# Agregar:
0 2 * * * /opt/inversiones_ramon/backup_db.sh >> /opt/inversiones_ramon/logs/backup.log 2>&1
```

Restaurar un respaldo (en caso de necesitarlo):

```bash
pg_restore -h localhost -U ramon_user -d inversiones_ramon -c inversiones_ramon_FECHA.dump
```

> Idealmente, copia periódicamente la carpeta `backups/` a almacenamiento
> externo (otro servidor, S3, etc.) — un respaldo que vive en el mismo
> disco que la base de datos no protege contra una falla del disco.

---

## 12. Firewall básico

```bash
sudo apt install -y ufw
sudo ufw allow OpenSSH
sudo ufw allow 'Nginx Full'   # 80 y 443
sudo ufw enable
sudo ufw status
```

PostgreSQL (puerto 5432) y gunicorn (socket Unix) no necesitan reglas: solo
escuchan en `localhost`/socket local, no están expuestos a internet.

---

## Actualizaciones futuras

Cada vez que despliegues una nueva versión del código:

```bash
cd /opt/inversiones_ramon
source venv/bin/activate
git pull        # o el método que uses para actualizar el código

pip install -r requirements.txt
python manage.py migrate
python manage.py collectstatic --noinput

sudo systemctl restart inversiones_ramon
```
