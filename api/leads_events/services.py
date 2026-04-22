"""
api/leads/events/services.py

Service de construction du tree pour React Flow.
"""

import math
from .models import LeadEvent


class LeadEventService:

    @staticmethod
    def log(lead, event_code, actor=None, data=None, note="",
            parent_event=None, attachment_ids=None):
        return LeadEvent.log(
            lead=lead,
            event_code=event_code,
            actor=actor,
            data=data,
            note=note,
            parent_event=parent_event,
            attachment_ids=attachment_ids,
        )

    @staticmethod
    def get_timeline_for_react_flow(lead_id: int) -> dict:
        """
        Retourne { nodes, edges } au format React Flow pour un lead donné.

        Calcule automatiquement les positions si position_x/y sont à 0.
        Utilise un layout en arbre hiérarchique (Reingold–Tilford simplifié).
        """
        events = (
            LeadEvent.objects
            .filter(lead_id=lead_id)
            .select_related("event_type", "actor")
            .prefetch_related("attachments", "children")
            .order_by("occurred_at")
        )

        events_list = list(events)

        if not events_list:
            return {"nodes": [], "edges": []}

        # ── Auto-layout si aucune position n'a été définie ──
        needs_layout = all(e.position_x == 0.0 and e.position_y == 0.0 for e in events_list)
        if needs_layout:
            LeadEventService._auto_layout(events_list)

        nodes = []
        edges = []

        for event in events_list:
            actor_name = event.actor.get_full_name() if event.actor else "Système"
            attachments_data = [
                {
                    "id": doc.id,
                    "url": doc.url,
                    "type": doc.document_type.name if doc.document_type else None,
                }
                for doc in event.attachments.all()
            ]

            nodes.append({
                "id": str(event.id),
                "type": "leadEventNode",        # custom node React Flow
                "position": {
                    "x": event.position_x,
                    "y": event.position_y,
                },
                "data": {
                    "id": event.id,
                    "eventCode": event.event_type.code,
                    "eventLabel": event.event_type.label,
                    "actorName": actor_name,
                    "actorId": event.actor_id,
                    "note": event.note,
                    "data": event.data,
                    "occurredAt": event.occurred_at.isoformat(),
                    "attachments": attachments_data,
                    "attachmentsCount": len(attachments_data),
                    "isSystem": event.event_type.is_system,
                    "parentId": str(event.parent_event_id) if event.parent_event_id else None,
                },
                "draggable": True,
            })

            if event.parent_event_id:
                edges.append({
                    "id": f"e{event.parent_event_id}-{event.id}",
                    "source": str(event.parent_event_id),
                    "target": str(event.id),
                    "type": "smoothstep",
                    "animated": False,
                    "style": {"stroke": "#334155", "strokeWidth": 1.5},
                    "markerEnd": {
                        "type": "arrowclosed",
                        "color": "#334155",
                    },
                })

        return {"nodes": nodes, "edges": edges}

    @staticmethod
    def _auto_layout(events: list) -> None:
        """
        Calcule un layout hiérarchique simple (top→down).
        Modifie les positions en mémoire (pas de sauvegarde DB ici).

        Algorithme :
            - Niveau 0 : racines (pas de parent)
            - Niveau N : enfants du niveau N-1
            - Espacement horizontal : 280px, vertical : 180px
        """
        NODE_W = 280
        NODE_H = 180

        # Index par id
        by_id = {e.id: e for e in events}

        # Calcul des niveaux
        levels: dict[int, list] = {}

        def get_level(event_id: int, visited=None) -> int:
            if visited is None:
                visited = set()
            if event_id in visited:
                return 0
            visited.add(event_id)
            event = by_id.get(event_id)
            if not event or not event.parent_event_id:
                return 0
            return get_level(event.parent_event_id, visited) + 1

        for e in events:
            lvl = get_level(e.id)
            levels.setdefault(lvl, []).append(e)

        # Assignation positions
        for lvl, lvl_events in levels.items():
            total_width = len(lvl_events) * NODE_W
            start_x = -total_width / 2
            for i, event in enumerate(lvl_events):
                event.position_x = start_x + i * NODE_W + NODE_W / 2
                event.position_y = lvl * NODE_H

    @staticmethod
    def update_node_position(event_id: int, x: float, y: float) -> None:
        """
        Met à jour la position d'un nœud dans le canvas React Flow.
        Seule modification autorisée sur un LeadEvent immuable.
        """
        LeadEvent.objects.filter(pk=event_id).update(
            position_x=x,
            position_y=y,
        )