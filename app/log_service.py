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
        self.player_state = "idle"  # Default state is idle

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
        # Default location values if not available
        location_guid = "none"
        location_name = "none"
        is_multiple = False
        
        # Try to get location data from player if available
        try:
            if hasattr(self.websocket_client, 'player') and self.websocket_client.player:
                player = self.websocket_client.player
                if hasattr(player, 'location_data') and player.location_data:
                    location_guid = player.location_data.get("guid", "none")
                    location_name = player.location_data.get("name", "none")
                    is_multiple = player.location_data.get("isMultiple", False)
        except Exception as e:
            logger.error(f"Error getting location data: {e}")

        log_value = {
            "type": type,
            "message": message,
            "locationGuid": location_guid,
            "locationName": location_name,
            "version": "1.0.0",  # Replace with actual version
            "os": platform.system(),
            "osVersion": platform.version(),
            "platform": platform.platform(),
            "diskFree": "unknown",  # Replace with actual disk free space
            "deviceManufacturer": "unknown",  # Replace with actual manufacturer
            "clientId": self.client_id,
            "status": self.player_state,  # Use the current player state
            "userId": self.websocket_client.user_id,  # Use user_id from WebSocketClient
            "page": page,
            "isMultiple": 1 if is_multiple else 0,
        }
        return log_value

    def send_log(self, type, message, page="player"):
        log_model = self.build_log_model(type, message, page)
        self.send_websocket_action(log_model["status"], log_model)

    def set_player_state(self, state):
        """
        Set the current player state and send a state update via websocket.
        
        Args:
            state: One of 'idle', 'playing', 'stopped', or 'muted'
        """
        if state not in ["idle", "playing", "stopped", "muted"]:
            logger.warning(f"Invalid player state: {state}. Using 'idle' instead.")
            state = "idle"
            
        self.player_state = state
        # Send a state update message
        self.send_log("info", f"Player state changed to {state}")

    def send_player_state(self):
        """
        Send the current player state via websocket without changing the log message.
        """
        log_model = self.build_log_model("info", f"Player state: {self.player_state}")
        self.send_websocket_action(self.player_state, log_model)

    def send_websocket_action(self, action, log_model):
        if self.websocket_client.ws and self.websocket_client.ws.sock and self.websocket_client.ws.sock.connected:
            try:
                self.websocket_client.ws.send(json.dumps({"action": action, **log_model}))
            except Exception as e:
                logger.error(f"Failed to send action: {e}")
        else:
            logger.error("WebSocket not connected")