import contextvars

# ContextVar pour stocker l'utilisateur courant de manière thread-safe et async-safe
_current_user = contextvars.ContextVar("current_user", default=None)

def set_current_user(user):
    """Définit l'utilisateur pour le contexte actuel."""
    return _current_user.set(user)

def get_current_user():
    """Récupère l'utilisateur du contexte actuel."""
    return _current_user.get()
