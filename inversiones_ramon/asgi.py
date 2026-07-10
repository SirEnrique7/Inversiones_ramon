import os
from django.core.asgi import get_asgi_application
from .settings_selector import resolver_settings_module

os.environ.setdefault('DJANGO_SETTINGS_MODULE', resolver_settings_module())
application = get_asgi_application()
