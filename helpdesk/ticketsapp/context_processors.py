from django.utils import timezone
from .rbac import get_user_role


def global_context(request):
    """Expose commonly used context variables to templates."""
    user_role = None
    if request.user.is_authenticated:
        user_role = get_user_role(request.user)
    return {
        'user_role': user_role,
        'current_time': timezone.now(),
    }

