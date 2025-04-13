# app/log_service.py
import platform
import json
import uuid
import os
import logging

logger = logging.getLogger("naistro-player")

class LogService:
    def __init__(self, websocket_client):
        self.websocket_client = websocket_client
        self.client_id = self._get_client_id()

    def _get_client_id(self):
        """Retrieve or generate a client ID and store it in a cache."""
        cache_file = "client_id_cache.txt"
        if os.path.exists(cache_file):
            with open(cache_file, "r") as file:
                client_id = file.read().strip()
                if client_id:
                    return client_id

        # Generate a new client ID if not found
        client_id = str(uuid.uuid4())
        with open(cache_file, "w") as file:
            file.write(client_id)
        return client_id

    def build_log_model(self, type, message, page="player"):
        # You can replace these with actual values from your app
        active_location = {"guid": "some-guid", "name": "some-location", "isMultiple": False}
        player_current_state = "idle"

        log_value = {
            "type": type,
            "message": message,
            "locationGuid": active_location.get("guid", "none"),
            "locationName": active_location.get("name", "none"),
            "version": "1.0.0",  # Replace with actual version
            "os": platform.system(),
            "osVersion": platform.version(),
            "platform": platform.platform(),
            "diskFree": "unknown",  # Replace with actual disk free space
            "deviceManufacturer": "unknown",  # Replace with actual manufacturer
            "clientId": self.client_id,
            "status": player_current_state,
            "userId": self.websocket_client.user_id,  # Use user_id from WebSocketClient
            "page": page,
            "isMultiple": 1 if active_location.get("isMultiple") else 0,
        }
        return log_value

    def send_log(self, type, message, page="player"):
        log_model = self.build_log_model(type, message, page)
        self.send_websocket_action(log_model["status"], log_model)

    def send_websocket_action(self, action, log_model):
        if self.websocket_client.ws and self.websocket_client.ws.sock and self.websocket_client.ws.sock.connected:
            try:
                self.websocket_client.ws.send(json.dumps({"action": action, **log_model}))
            except Exception as e:
                logger.error(f"Failed to send action: {e}")
        else:
            logger.error("WebSocket not connected")