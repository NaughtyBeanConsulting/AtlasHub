import os
import sys

from django.apps import AppConfig

_SKIP_COMMANDS = {
    'migrate', 'makemigrations', 'test', 'collectstatic',
    'createsuperuser', 'shell', 'dbshell', 'check',
    'showmigrations', 'sqlmigrate', 'inspectdb', 'dumpdata', 'loaddata',
    'seed_demo',
}


class WhatsappConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'whatsapp'
    verbose_name = 'WhatsApp'

    def ready(self):
        cmd = sys.argv[1] if len(sys.argv) > 1 else ''
        if cmd in _SKIP_COMMANDS:
            return

        # With Django's dev-server autoreloader, ready() fires twice.
        # The outer process manages reloading; the inner (RUN_MAIN=true) serves.
        if 'runserver' in sys.argv and not os.environ.get('RUN_MAIN'):
            return

        try:
            from .scheduler import scheduler
            scheduler.start()
        except Exception:
            pass
