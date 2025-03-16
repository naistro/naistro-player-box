import yaml
import time
from app.auth import get_auth_token, save_token
from app.api import fetch_locations 
# , fetch_playlist, fetch_location
from app.logger import setup_logger
# from app.player import start_player
# from app.interruption_storage import InterruptionStorage

# Initialize logger
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
    # logger.info("Starting application...")

    USER_ID = config["credentials"]["username"]
    logger.info(f"Using User ID: {USER_ID}")

    # Step 1: Authenticate and store the token
    # logger.info("Authenticating with AWS Cognito...")
    id_token, _, _ = get_auth_token()
    if not id_token:
        logger.error("Authentication failed. Exiting...")
        return

    save_token(id_token)
    logger.info("Authentication successful.")

    # Step 2: Fetch locations
    # logger.info("Fetching available locations...")
    locations = fetch_locations()
    if not locations:
        logger.error("No locations found. Exiting...")
        return

    logger.info(f"Locations retrieved: {len(locations)} locations found.")

    # # Select the second location for now
    # selected_location = locations[1]
    # location_id = selected_location.get("guid")  # Assuming the location object has a GUID field

    # logger.info(f"Selected location: {selected_location.get('name')} (ID: {location_id})")

    # Set up player instance (without starting playback yet)
    from app.player import Player
    player = Player()
    
    # Set up SQS client
    from app.sqs_client import SQSClient
    sqs_client = SQSClient(player, USER_ID)
    sqs_client.start()
    
    logger.info("Player ready in idle state. Waiting for SQS commands...")
    
    # Keep the application running
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        logger.info("Shutting down...")
        sqs_client.stop()
        player.stop()

    # # Step 3: Fetch playlist for the selected location
    # # logger.info(f"Fetching playlist for location {location_id}...")
    # playlistData = fetch_playlist(location_id)
    # locationData = fetch_location(location_id)

    # if not playlistData["events"]:
    #     logger.error("No tracks found in the playlist. Exiting...")
    #     return

    # # Step 4: Download and cache interruption files
    # storage = InterruptionStorage()
    # if not storage.load_interruption_files(locationData):
    #     logger.error("Failed to load interruption files. Exiting...")
    #     return
    
    # logger.info("Interruption files loaded successfully.")

    # logger.info(f"Playlist loaded: {len(playlistData["events"])} tracks found.")

    # # Step 5: Start playing the playlist
    # start_player(playlistData["events"], playlistData["locationOffset"], locationData)

if __name__ == "__main__":
    main()
