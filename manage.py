#!/usr/bin/env python
import os
import sys

def main():
    # Selección automática: usa inversiones_ramon.settings_prod si
    # DJANGO_ENV=production está en el entorno/.env, o lo que ya esté
    # definido explícitamente en DJANGO_SETTINGS_MODULE. Ver
    # inversiones_ramon/settings_selector.py para los detalles.
    from inversiones_ramon.settings_selector import resolver_settings_module
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', resolver_settings_module())
    try:
        from django.core.management import execute_from_command_line
    except ImportError as exc:
        raise ImportError(
            "No se pudo importar Django. "
            "¿Está el entorno virtual activado?"
        ) from exc
    execute_from_command_line(sys.argv)

if __name__ == '__main__':
    main()
