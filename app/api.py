import requests
import yaml
from app.auth import get_auth_token, save_token, load_token
from app.logger import setup_logger

# Load configuration
with open("config/config.yaml", "r") as file:
    config = yaml.safe_load(file)

LOCATIONS_URL = config["api"]["locations_url"]
PLAYLISTS_URL_PREFIX = config["api"]["playlists_url_prefix"]

logger = setup_logger()

def get_headers():
    """Get headers with authentication token"""
    token = load_token()
    if not token:
        logger.info("Fetching new authentication token...")
        id_token, _, _ = get_auth_token()
        if id_token:
            save_token(id_token)
            token = id_token
        else:
            logger.error("Failed to retrieve authentication token")
            return None

    return {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }

def fetch_locations():
    """Fetch list of locations from API"""
    headers = get_headers()
    if not headers:
        return None
    

    try:
        response = requests.get(LOCATIONS_URL, headers=headers)
        response.raise_for_status()
        data = response.json()

        if "payload" in data:
            return data["payload"]
        else:
            logger.error("Invalid locations API response format")
            return None

    except requests.exceptions.RequestException as e:
        logger.error(f"Failed to fetch locations: {e}")
        return None

def fetch_playlist(location_id):
    """Fetch playlist for a given location"""
    headers = get_headers()
    if not headers:
        return None

    # Construct the URL with the location_id dynamically
    playlist_url = f"{PLAYLISTS_URL_PREFIX}{location_id}/new-playlist"
    
    # Add query parameters
    params = {
        "encrypted": "true",
        "timezoneSecondsOffset": -3600,
        "minSecondsCachedExpected": 90000,
        "isPlaylists": "true",
        "test": "false",
        "prayerDurationInMilliseconds": 60,
        "silenceDurationInMilliseconds": 30000
    }

    try:
        response = requests.get(playlist_url, headers=headers, params=params)
        response.raise_for_status()

        data = response.json()

        payload = data["payload"]
        if "events" in payload:
            return payload["events"]
        else:
            logger.error("Invalid playlist API response format")
            return None

    except requests.exceptions.RequestException as e:
        logger.error(f"Failed to fetch playlist: {e}")
        return None

