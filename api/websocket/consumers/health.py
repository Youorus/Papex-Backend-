from channels.generic.websocket import AsyncJsonWebsocketConsumer


class HealthCheckConsumer(AsyncJsonWebsocketConsumer):
    async def connect(self):
        # Pas de groupe Redis, juste accept
        await self.accept()

    async def receive_json(self, content):
        # Réponse au ping
        if content.get("type") == "ping":
            await self.send_json({"type": "pong"})

    async def disconnect(self, code):
        # Rien à faire
        pass
