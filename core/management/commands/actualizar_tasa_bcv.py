# ══════════════════════════════════════════════════════════════
# management/commands/actualizar_tasa_bcv.py
#
# Comando Django que actualiza la tasa BCV del día.
# Reemplaza la necesidad de Celery para tareas programadas simples.
#
# USO MANUAL:
#   python manage.py actualizar_tasa_bcv
#   python manage.py actualizar_tasa_bcv --forzar          # actualiza aunque ya exista
#   python manage.py actualizar_tasa_bcv --verbosity 2     # modo detallado
#
# CONFIGURACIÓN CON CRON (Linux/VPS):
#   Agregar al crontab del sistema (crontab -e):
#   # Actualizar tasa BCV de lunes a viernes a las 9:00 AM (hora Venezuela)
#   0 9 * * 1-5 cd /ruta/al/proyecto && /ruta/a/venv/bin/python manage.py actualizar_tasa_bcv >> /var/log/inversiones_ramon_bcv.log 2>&1
#
# CONFIGURACIÓN CON TASK SCHEDULER (Windows Server):
#   Acción: C:\ruta\venv\Scripts\python.exe manage.py actualizar_tasa_bcv
#   Directorio: C:\ruta\al\proyecto
#   Desencadenador: Diario, 9:00 AM, de lunes a viernes
#
# SALIDA:
#   Exit 0 → OK (tasa obtenida o ya existía)
#   Exit 1 → Error (no se pudo obtener la tasa del BCV)
# ══════════════════════════════════════════════════════════════

import sys
import logging
from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Actualiza la tasa de cambio BCV del día consultando bcv.org.ve'

    def add_arguments(self, parser):
        parser.add_argument(
            '--forzar',
            action='store_true',
            default=False,
            help='Fuerza la actualización aunque ya exista una tasa para hoy.',
        )

    def handle(self, *args, **options):
        from core.models import TasaCambio, AuditoriaAccion
        from core.bcv_scraper import extraer_tasa_bcv

        verboso  = options['verbosity'] >= 2
        forzar   = options['forzar']
        hoy      = timezone.now().date()

        if verboso:
            self.stdout.write(f'[actualizar_tasa_bcv] Fecha: {hoy}')

        # ── Verificar si ya existe tasa para hoy ──────────────────────────
        existente = TasaCambio.objects.filter(fecha=hoy).first()
        if existente and not forzar:
            self.stdout.write(
                self.style.SUCCESS(
                    f'✓ Tasa del {hoy} ya registrada: Bs. {existente.tasa_bs_usd} / USD. '
                    f'Use --forzar para sobrescribir.'
                )
            )
            return  # Exit 0

        # ── Extraer tasa del BCV ───────────────────────────────────────────
        if verboso:
            self.stdout.write('  Consultando bcv.org.ve…')

        tasa = extraer_tasa_bcv()

        if tasa is None:
            # Intentar usar la última tasa como fallback
            ultima = TasaCambio.objects.order_by('-fecha').first()
            self.stderr.write(
                self.style.ERROR(
                    f'✗ No se pudo obtener la tasa del BCV para {hoy}.'
                )
            )
            if ultima:
                self.stderr.write(
                    f'  Última tasa disponible: Bs. {ultima.tasa_bs_usd} del {ultima.fecha}.'
                )
            # Registrar fallo en auditoría
            try:
                AuditoriaAccion.registrar(
                    usuario=None, accion='tasa_bcv',
                    descripcion=f'FALLO: No se pudo obtener la tasa BCV del día {hoy} via cron.',
                )
            except Exception:
                pass
            sys.exit(1)  # Exit 1 para que cron/monitoreo detecte el fallo

        # ── Guardar o actualizar ───────────────────────────────────────────
        if existente and forzar:
            existente.tasa_bs_usd = tasa
            existente.fuente      = 'bcv.org.ve (actualización forzada)'
            existente.save(update_fields=['tasa_bs_usd', 'fuente'])
            accion_desc = f'Tasa BCV FORZADA para {hoy}: Bs. {tasa} / USD'
            if verboso:
                self.stdout.write(f'  Tasa anterior: Bs. {existente.tasa_bs_usd}')
        else:
            TasaCambio.objects.create(
                fecha=hoy,
                tasa_bs_usd=tasa,
                fuente='bcv.org.ve (cron)',
            )
            accion_desc = f'Tasa BCV actualizada via cron para {hoy}: Bs. {tasa} / USD'

        # ── Auditoría ──────────────────────────────────────────────────────
        try:
            AuditoriaAccion.registrar(
                usuario=None, accion='tasa_bcv',
                descripcion=accion_desc,
            )
        except Exception as exc:
            # El fallo en auditoría no debe interrumpir el proceso
            logger.warning('actualizar_tasa_bcv: no se pudo registrar auditoría — %s', exc)

        self.stdout.write(
            self.style.SUCCESS(
                f'✓ Tasa BCV actualizada: Bs. {tasa} / USD  [{hoy}]'
            )
        )
