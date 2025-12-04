from django.contrib.auth.models import User
from django.db.models.signals import post_save
from django.dispatch import receiver

from .models import Profile


@receiver(post_save, sender=User)
def ensure_profile_exists(sender, instance, created, **kwargs):
    """Automatically provision a profile for every new user."""
    if not created:
        return

    default_role = 'PROJECT_MANAGER' if instance.is_superuser else 'ISSUE_REPORTER'
    Profile.objects.get_or_create(
        user=instance,
        defaults={'role': default_role}
    )

