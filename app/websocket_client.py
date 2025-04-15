# app/websocket_client.py
import websocket
import json
import logging
import threading
import time
import yaml
import urllib.parse
from datetime import datetime
from app.log_service import LogService

logger = logging.getLogger("naistro-player")

try:
    with open("config/config.yaml", "r") as file:
        config = yaml.safe_load(file)
    with open("config/auth.yaml", "r") as file:
        auth_config = yaml.safe_load(file)
    logger.info("Configuration loaded successfully.")
except Exception as e:
    logger.error(f"Failed to load configuration: {e}")
    raise

class WebSocketClient:
    """WebSocket client for player box remote control"""
    
    def __init__(self, player, user_id):
        """
        Initialize WebSocket client
        
        Args:
            player: Player instance to control
            user_id: User ID to identify this client
        """
        self.player = player
        self.user_id = user_id
        
        # Configure WebSocket parameters
        self.websocket_url = config["api"]["websocket_url"]
        self.token = None
        self.ws = None
        
        self.running = False
        self.connection_thread = None
        self.ping_thread = None
        
        # Initialize LogService
        self.log_service = LogService(self)
        
        # Connect player to log service
        if self.player:
            self.player.set_websocket_client(self)
        
        # Player control commands mapping
        self.control_actions = {
            "start-play": self._handle_start_play,
            "continue-play": self._handle_play_pause,
            "pause": self._handle_play_pause,
            "stop": self._handle_stop,
            "refresh": self._handle_refresh,
            "volume-up": self._handle_volume_up,
            "volume-down": self._handle_volume_down,
            "play-birthday-track": self._handle_birthday_track
        }
    
    def start(self, token=None):
        """
        Start WebSocket connection
        
        Args:
            token: JWT token for authentication
        """
        if self.connection_thread and self.connection_thread.is_alive():
            logger.info("WebSocket client already running")
            return
        
        self.token = token
        self.running = True
        
        # Start connection thread
        self.connection_thread = threading.Thread(target=self._maintain_connection)
        self.connection_thread.daemon = True
        self.connection_thread.start()
        
        logger.info(f"WebSocket client started for user ID: {self.user_id}")
    
    def stop(self):
        """Stop WebSocket connection"""
        self.running = False
        
        if self.ws:
            self.ws.close()
        
        if self.connection_thread:
            self.connection_thread.join(timeout=2)
            
        if self.ping_thread:
            self.ping_thread.join(timeout=2)
            
        logger.info("WebSocket client stopped")
    
    def _maintain_connection(self):
        """Maintain WebSocket connection and reconnect if necessary"""
        reconnect_delay = 1
        max_reconnect_delay = 60
        
        while self.running:
            try:
                self._connect()
                
                # Reset reconnect delay on successful connection
                reconnect_delay = 1
                
                # Wait until the connection is closed
                while self.running and self.ws.sock and self.ws.sock.connected:
                    time.sleep(1)
                
                logger.info("WebSocket connection closed, reconnecting...")
                
            except Exception as e:
                logger.error(f"WebSocket connection error: {e}", exc_info=True)
                
                # Implement exponential backoff for reconnection
                time.sleep(reconnect_delay)
                reconnect_delay = min(reconnect_delay * 2, max_reconnect_delay)
    
    def _connect(self):
        """Establish WebSocket connection"""
        if not self.token:
            logger.error("No authentication token available")
            return False
        
        # Prepare session metadata
        session_meta = self._get_session_metadata()
        
        # Construct WebSocket URL with token and metadata
        encoded_token = urllib.parse.quote(self.token)
        encoded_meta = urllib.parse.quote(json.dumps(session_meta))
        ws_url = f"{self.websocket_url}?token={encoded_token}&meta={encoded_meta}"
        
        # Initialize WebSocket connection
        try:
            # Set up WebSocket with callbacks
            self.ws = websocket.WebSocketApp(
                ws_url,
                on_open=self._on_open,
                on_message=self._on_message,
                on_error=self._on_error,
                on_close=self._on_close
            )
            
            # Start WebSocket in a new thread
            ws_thread = threading.Thread(target=self.ws.run_forever)
            ws_thread.daemon = True
            ws_thread.start()
            
            # Wait for connection to be established
            timeout = 10
            start_time = time.time()
            while not (self.ws.sock and self.ws.sock.connected) and time.time() - start_time < timeout:
                time.sleep(0.1)
            
            if not (self.ws.sock and self.ws.sock.connected):
                logger.error("Failed to establish WebSocket connection within timeout")
                return False
            
            return True
            
        except Exception as e:
            logger.error(f"Error establishing WebSocket connection: {e}", exc_info=True)
            return False
    
    def _get_session_metadata(self):
        """Get session metadata for WebSocket connection using LogModel"""
        log_model = self.log_service.build_log_model(
            type="info",
            message="Session started",
            page="player"
        )
        return log_model
    
    def _start_ping_thread(self):
        """Start thread to send ping messages periodically"""
        if self.ping_thread and self.ping_thread.is_alive():
            return
            
        self.ping_thread = threading.Thread(target=self._ping_loop)
        self.ping_thread.daemon = True
        self.ping_thread.start()
        logger.info("Started WebSocket ping thread")
    
    def _ping_loop(self):
        """Send ping messages periodically to keep connection alive"""
        while self.running and self.ws and self.ws.sock and self.ws.sock.connected:
            try:
                log_model = self.log_service.build_log_model(
                    type="info",
                    message="keep-alive ping",
                    page="player"
                )
                ping_data = {
                    "action": "ping",
                    **log_model
                }
                self.ws.send(json.dumps(ping_data))
                logger.debug("Sent keep-alive ping")
                
                # Wait before sending next ping
                time.sleep(20)  # Same as React Native implementation
                
            except Exception as e:
                logger.error(f"Error sending ping: {e}", exc_info=True)
                break
    
    def _on_open(self, ws):
        """Callback when WebSocket connection is opened"""
        logger.info(f"WebSocket connection established at {datetime.now().isoformat()}")
        self.log_service.send_log("info", "WebSocket connection established")
        self._start_ping_thread()
    
    def _on_message(self, ws, message):
        """Callback when message is received from WebSocket"""
        logger.info(f"WebSocket message received: {message}")
        
        try:
            # Parse message
            json_response = json.loads(message)
            
            # Extract control command and location GUID if present
            message_data = json_response.get("message", {})
            control = message_data.get("control")
            location_guid = message_data.get("locationGuid")
            
            logger.info(f"Processing command: {control}, location: {location_guid}")
            
            # Execute command if supported
            if control in self.control_actions:
                self.control_actions[control](location_guid)
            else:
                logger.warning(f"Unknown command: {control}")
                
        except json.JSONDecodeError:
            logger.error("Invalid JSON in message", exc_info=True)
        except Exception as e:
            logger.error(f"Error processing message: {e}", exc_info=True)
    
    def _on_error(self, ws, error):
        """Callback when WebSocket error occurs"""
        logger.error(f"WebSocket error: {error}", exc_info=True)
    
    def _on_close(self, ws, close_status_code, close_reason):
        """Callback when WebSocket connection is closed"""
        logger.info(f"WebSocket connection closed: {close_status_code}, {close_reason}")
    
    def send_action(self, action, message, page="player"):
        """
        Send action to WebSocket server
        
        Args:
            action: Action name
            message: Log message
            page: Page context
        """
        if not self.ws or not self.ws.sock or not self.ws.sock.connected:
            logger.warning("Cannot send action: WebSocket not connected")
            return False
            
        try:
            # Use LogService to build log model
            log_model = self.log_service.build_log_model(
                type=action,
                message=message,
                page=page
            )
            
            # Send message
            self.ws.send(json.dumps({"action": action, **log_model}))
            logger.debug(f"Sent action: {action}")
            return True
            
        except Exception as e:
            logger.error(f"Error sending action: {e}", exc_info=True)
            return False   

    # Player control handlers    
    def _handle_start_play(self, location_guid):
        """Handle start-play command"""
        if location_guid:
            self.player.start_playback_by_guid(location_guid)
        else:
            logger.warning("Cannot start playback: No location GUID provided")
    
    def _handle_play_pause(self, location_guid=None):
        """Handle play/pause command"""
        # Toggle play/pause state
        self.player.play_pause()
    
    def _handle_stop(self, location_guid=None):
        """Handle stop command"""
        self.player.stop()
    
    def _handle_refresh(self, location_guid=None):
        """Handle refresh command"""
        # Implement refresh logic if needed
        logger.info("Refresh command received")
    
    def _handle_volume_up(self, location_guid=None):
        """Handle volume-up command"""
        current_volume = self.player.volume
        new_volume = min(current_volume + 10, 100)
        self.player.set_volume(new_volume)
    
    def _handle_volume_down(self, location_guid=None):
        """Handle volume-down command"""
        current_volume = self.player.volume
        new_volume = max(current_volume - 10, 0)
        self.player.set_volume(new_volume)
    
    def _handle_birthday_track(self, location_guid=None):
        """Handle play-birthday-track command"""
        # Implement birthday track playback logic
        logger.info("Birthday track command received")