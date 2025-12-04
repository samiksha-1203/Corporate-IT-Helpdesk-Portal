from django.apps import AppConfig


class TicketsappConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'ticketsapp'

    def ready(self):
        from . import signals  # noqa: F401
        from django.db.models.signals import post_migrate
        from django.apps import apps

        def _bootstrap_admin(**kwargs):
            import os
            u = os.environ.get('DJANGO_SUPERUSER_USERNAME')
            p = os.environ.get('DJANGO_SUPERUSER_PASSWORD')
            e = os.environ.get('DJANGO_SUPERUSER_EMAIL')
            if not (u and p and e):
                return
            User = apps.get_model('auth', 'User')
            try:
                if not User.objects.filter(username=u).exists():
                    User.objects.create_superuser(username=u, email=e, password=p)
            except Exception:
                pass

        post_migrate.connect(_bootstrap_admin, dispatch_uid='ticketsapp_bootstrap_admin')
