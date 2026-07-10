import os
from django.core.wsgi import get_wsgi_application
from .settings_selector import resolver_settings_module

os.environ.setdefault('DJANGO_SETTINGS_MODULE', resolver_settings_module())
application = get_wsgi_application()
