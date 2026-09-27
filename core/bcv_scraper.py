# ══════════════════════════════════════════════════════════════
# BCV SCRAPER — Extracción automática de la tasa oficial
# ══════════════════════════════════════════════════════════════

import re
import logging
import requests
import urllib3
from decimal import Decimal, InvalidOperation

from django.db import connection, IntegrityError

logger = logging.getLogger(__name__)

# Silenciar advertencias SSL (el sitio del BCV tiene certificados problemáticos)
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)


def extraer_tasa_bcv() -> Decimal | None:
    """
    GET a bcv.org.ve con verify=False para ignorar errores de certificado.
    Devuelve el valor USD como Decimal, o None si no se pudo extraer.
    """
    url = "https://www.bcv.org.ve/"
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/120.0.0.0 Safari/537.36"
        )
    }

    try:
        resp = requests.get(url, headers=headers, timeout=15, verify=False)
        resp.raise_for_status()
        html = resp.text

        # ── Patrón primario ──────────────────────────────────────────────────
        # Busca el contenedor id="dolar" y captura el primer número con coma
        # decimal en formato venezolano.
        # Cubre: "36,50" | "128,30" | "1.250,00" (con punto de miles)
        # NOTA: usamos re.compile con cadena ordinaria + raw string concatenados
        # para que \d sea el metacarácter "dígito" y no el literal backslash-d.
        patron_primario = re.compile(
            "id=[\"']dolar[\"'].*?" + r"(\d{1,3}(?:\.\d{3})?,\d{2,4})",
            re.DOTALL | re.IGNORECASE,
        )
        match = patron_primario.search(html)

        if not match:
            # ── Fallback ─────────────────────────────────────────────────────
            # Si el HTML cambia estructura, buscamos cualquier número en
            # formato venezolano precedido de la cadena "USD".
            patron_fallback = re.compile(
                r"USD.*?(\d[\d.]*,\d{2,4})",
                re.DOTALL | re.IGNORECASE,
            )
            match = patron_fallback.search(html)

        if not match:
            logger.warning("bcv_scraper: no se encontró la tasa en el HTML del BCV.")
            return None

        raw = match.group(1).strip()
        # Formato venezolano: puntos como separador de miles, coma como decimal
        # Ejemplo: "1.234,50" → "1234.50"
        raw = raw.replace(".", "").replace(",", ".")
        return Decimal(raw)

    except requests.RequestException as exc:
        logger.warning("bcv_scraper: error de red al consultar el BCV — %s", exc)
        return None
    except InvalidOperation as exc:
        logger.warning("bcv_scraper: valor extraído no es un Decimal válido — %s", exc)
        return None


def actualizar_tasa_hoy():
    """
    Verifica si ya existe una tasa para hoy.
    Si no, la extrae del BCV y la persiste en TasaCambio.

    IMPORTANTE: esta función puede ejecutarse en un hilo secundario (Thread).
    Por eso cierra explícitamente la conexión de BD al terminar para que
    Django no deje conexiones abiertas huérfanas fuera del ciclo request/response
    (evita agotar el pool con CONN_MAX_AGE activo).

    Devuelve: (tasa: Decimal | None, fue_creada: bool)
    """
    # La importación diferida evita import circular al arrancar Django
    from django.utils import timezone
    from core.models import TasaCambio, AuditoriaAccion

    try:
        hoy = timezone.now().date()

        existente = TasaCambio.objects.filter(fecha=hoy).first()
        if existente:
            return existente.tasa_bs_usd, False

        tasa = extraer_tasa_bcv()
        if tasa:
            try:
                TasaCambio.objects.create(
                    fecha=hoy,
                    tasa_bs_usd=tasa,
                    fuente="bcv.org.ve",
                )
            except IntegrityError:
                # Otro hilo/proceso ganó la carrera y ya creó la tasa de hoy
                # entre nuestro chequeo `if existente` y este create() —
                # perfectamente normal cuando varios usuarios inician sesión
                # casi al mismo tiempo y cada login dispara su propio hilo.
                # No es un error real: simplemente usamos la que ya quedó
                # guardada, sin propagar una excepción que ensuciaría los
                # logs con un traceback de un caso ya resuelto.
                existente = TasaCambio.objects.filter(fecha=hoy).first()
                return (existente.tasa_bs_usd, False) if existente else (tasa, False)

            try:
                AuditoriaAccion.registrar(
                    usuario=None,
                    accion="tasa_bcv",
                    descripcion=f"Tasa BCV actualizada automáticamente: Bs. {tasa} / USD",
                )
            except Exception:
                # Un fallo en la auditoría no debe revertir la tasa guardada
                logger.exception("bcv_scraper: no se pudo registrar la auditoría de la tasa.")

            return tasa, True

        # Scraping fallido: usar la última tasa disponible como salvavidas
        ultima = TasaCambio.objects.order_by("-fecha").first()
        if ultima:
            return ultima.tasa_bs_usd, False

        return None, False

    finally:
        # Cierre explícito de la conexión de BD para hilos no gestionados por Django.
        # En el hilo principal del request esto es un no-op seguro porque Django
        # gestiona sus propias conexiones.
        connection.close()
