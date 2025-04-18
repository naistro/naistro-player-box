# app/api.py
import requests
import yaml
from app.auth import get_auth_token, save_token, load_token
import logging

logger = logging.getLogger("naistro-player")

# Load configuration
with open("config/config.yaml", "r") as file:
    config = yaml.safe_load(file)

LOCATIONS_URL = config["api"]["locations_url"]
CONTENT_TYPE = config["headers"]["content_type"]
PUBLIC_API_KEY = config["headers"]["public_api_key"]

def get_headers():
    """Get headers with authentication token"""
    token = load_token()
    if not token:
        logger.info("No token found. Fetching new authentication token...")
        id_token, _, _ = get_auth_token()
        if id_token:
            logger.info("New token fetched. Saving token...")
            save_token(id_token)
            token = id_token
        else:
            logger.error("Failed to retrieve authentication token")
            return None

    headers = {
        "Authorization": f"Bearer {token}",
        "x-api-key": PUBLIC_API_KEY,
        "Content-Type": CONTENT_TYPE
    }
    return headers

def fetch_locations():
    """Fetch list of locations from API"""
    headers = get_headers()
    if not headers:
        return None
    
    params = {
        "isPlaylists": "true",
    }

    try:
        response = requests.get(LOCATIONS_URL, headers=headers, params=params)
        response.raise_for_status()
        data = response.json()

        if "payload" in data:
            return data["payload"]
        else:
            logger.error("Invalid locations API response format")
            return None

    except requests.exceptions.HTTPError as e:
        # Log the response body for more details
        logger.error(f"HTTP Error: {e}")
        logger.error(f"Response Body: {e.response.text}")
        return None
    except requests.exceptions.RequestException as e:
        logger.error(f"Failed to fetch locations: {e}")
        return None


# fetch full location data
# https://api-prod.naistro.com/players/locations/41ee9eea-5c78-41fe-a608-1f60da0654b5?isPlaylists=true&test=false&prayerDurationInMilliseconds=30000&silenceDurationInMilliseconds=30000

def fetch_location(location_id):
    headers = get_headers()
    if not headers:
        return None

    location_url = f"{LOCATIONS_URL}/{location_id}"
    
    params = {
        "isPlaylists": "true",
        "test": "false",
        "prayerDurationInMilliseconds": 30000,
        "silenceDurationInMilliseconds": 30000
    }

    try:
        response = requests.get(location_url, headers=headers, params=params)
        response.raise_for_status()
        data = response.json()

        if "payload" in data:
            return data["payload"]
        else:
            logger.error("Invalid location API response format")
            return None

    except requests.exceptions.HTTPError as e:
        logger.error(f"HTTP Error: {e}")
        logger.error(f"Response Body: {e.response.text}")
        return None
    except requests.exceptions.RequestException as e:
        logger.error(f"Failed to fetch location: {e}")
        return None

def fetch_playlist(location_id):
    """Fetch playlist for a given location"""
    headers = get_headers()
    if not headers:
        return None

    # Construct the URL with the location_id dynamically
    playlist_url = f"{LOCATIONS_URL}/{location_id}/playlist"
    
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
            return payload
        else:
            logger.error("Invalid playlist API response format")
            return None

    except requests.exceptions.RequestException as e:
        logger.error(f"Failed to fetch playlist: {e}")
        return None

