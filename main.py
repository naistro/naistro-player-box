import time
from app.auth import get_auth_token, save_token, load_token
from app.api import fetch_locations, fetch_playlist
from app.logger import setup_logger
from app.player import start_player

# Initialize logger
logger = setup_logger()

def main():
    """Main workflow to authenticate, fetch locations, and get playlist"""
    # logger.info("Starting application...")

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

    # logger.info(f"Locations retrieved: {len(locations)} locations found.")

    # Select the second location for now
    selected_location = locations[1]
    location_id = selected_location.get("guid")  # Assuming the location object has a GUID field

    logger.info(f"Selected location: {selected_location.get('name')} (ID: {location_id})")

    # Step 3: Fetch playlist for the selected location
    # logger.info(f"Fetching playlist for location {location_id}...")
    playlist = fetch_playlist(location_id)

    if not playlist:
        logger.error("No tracks found in the playlist. Exiting...")
        return

    logger.info(f"Playlist loaded: {len(playlist)} tracks found.")

    # Step 4: Start playing the playlist
    # logger.info("Starting player...")
    start_player(playlist)

if __name__ == "__main__":
    main()
