from django.apps import AppConfig


class TicketsappConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'ticketsapp'

    def ready(self):
        from . import signals  # noqa: F401
        import os
        from django.contrib.auth import get_user_model
        u = os.environ.get('DJANGO_SUPERUSER_USERNAME')
        p = os.environ.get('DJANGO_SUPERUSER_PASSWORD')
        e = os.environ.get('DJANGO_SUPERUSER_EMAIL')
        if u and p and e:
            User = get_user_model()
            if not User.objects.filter(username=u).exists():
                try:
                    User.objects.create_superuser(username=u, email=e, password=p)
                except Exception:
                    pass
