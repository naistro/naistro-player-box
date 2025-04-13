import yaml
import time
from app.auth import get_auth_token, save_token
from app.api import fetch_locations 
from app.logger import setup_logger

logger = setup_logger()

try:
    with open("config/auth.yaml", "r") as file:
        config = yaml.safe_load(file)
    logger.info("Configuration loaded successfully.")
except Exception as e:
    logger.error(f"Failed to load configuration: {e}")
    raise

def main():
    """Main workflow to authenticate, fetch locations, and get playlist"""
    USER_ID = config["credentials"]["username"]
    logger.info(f"Using User ID: {USER_ID}")
    id_token, _, _ = get_auth_token()
    if not id_token:
        logger.error("Authentication failed. Exiting...")
        return

    save_token(id_token)
    logger.info("Authentication successful.")

    locations = fetch_locations()
    if not locations:
        logger.error("No locations found. Exiting...")
        return

    logger.info(f"Locations retrieved: {len(locations)} locations found.")

    # Set up player instance (without starting playback yet)
    from app.player import Player
    player = Player()
    
    # Set up WebSocket client
    from app.websocket_client import WebSocketClient
    ws_client = WebSocketClient(player, USER_ID)
    ws_client.start(id_token)  

    logger.info("Player ready in idle state. Waiting for SQS commands...")
    
    # Keep the application running
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        logger.info("Shutting down...")
        ws_client.stop()
        player.stop()

if __name__ == "__main__":
    main()
