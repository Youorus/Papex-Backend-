import json
from django.core.serializers.json import DjangoJSONEncoder
from django.db.models import Model

def get_model_diff(instance: Model, old_instance: Model = None):
    """
    Compare deux instances d'un modèle et retourne un dictionnaire des changements.
    Exemple: {"status": {"old": "A_CONTACTER", "new": "RDV_PLANIFIE"}}
    """
    diff = {}
    
    # Si pas d'ancienne instance, c'est une création
    if not old_instance:
        return diff

    # On liste les champs du modèle (on ignore les relations ManyToMany pour le diff simple)
    fields = [f.name for f in instance._meta.fields if not f.is_relation or f.many_to_one]
    
    for field in fields:
        old_val = getattr(old_instance, field)
        new_val = getattr(instance, field)
        
        if old_val != new_val:
            # Sérialisation basique pour JSON
            diff[field] = {
                "old": old_val if isinstance(old_val, (str, int, float, bool, type(None))) else str(old_val),
                "new": new_val if isinstance(new_val, (str, int, float, bool, type(None))) else str(new_val)
            }
            
    return diff
