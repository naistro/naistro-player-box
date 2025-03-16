# app/interruption_storage.py
from hashlib import md5
import os
import requests
import logging
import yaml

logger = logging.getLogger("naistro-player")

# Load configuration
with open("config/config.yaml", "r") as file:
    config = yaml.safe_load(file)

# Directory to store cached interruption tracks
CACHE_DIR = "cache/interruptions"
os.makedirs(CACHE_DIR, exist_ok=True)

class InterruptionStorage:
    def __init__(self):
        self.interruptions_loaded = False

    def download_interruption_track(self, url: str, md5: str) -> str | None:
        """
        Download an interruption track and cache it using the md5 as key.
        
        Args:
            url: The URL of the interruption track
            
        Returns:
            str | None: Path to the cached file if successful, None otherwise
        """
        try:
            cache_path = os.path.join(CACHE_DIR, md5)

            logger.info(f"Checking cache for interruption track {md5}")
            
            # If file already exists in cache, return its path
            if os.path.exists(cache_path):
                logger.info(f"Interruption track {md5} already in cache")
                return cache_path

            logger.info(f"Downloading interruption track from {url}")
            response = requests.get(url, stream=True)
            response.raise_for_status()

            with open(cache_path, "wb") as f:
                for chunk in response.iter_content(chunk_size=8192):
                    f.write(chunk)

            logger.info(f"Downloaded interruption track to {cache_path}")
            return cache_path

        except Exception as e:
            logger.error(f"Error downloading interruption track: {e}")
            return None

    def load_interruption_files(self, location_data: dict) -> bool:
        """
        Load all interruption files for a location
        
        Args:
            location_data: Location data containing interruption configurations
            
        Returns:
            bool: True if all files were loaded successfully, False otherwise
        """
        try:
            # Download prayer time audio if enabled
            if location_data.get("hasPrayerTime"):
                md5 = location_data.get("interruptions", {}).get('config', {}).get('prayerTimes', {})["md5"]
                if not self.download_interruption_track(location_data["normalisedPrayerTimeUrl"], md5):
                    logger.error("Failed to download prayer audio")
                    return False

            # Download birthday audio if enabled
            if location_data.get("isBdayEnabled"):
                md5 = location_data["bDayTrackMd5"]
                if not self.download_interruption_track(location_data["normalisedBdayTrackUrl"], md5):
                    logger.error("Failed to download birthday audio")
                    return False

            # Download campaign/ad audio files
            ads = location_data.get("interruptions", {}).get("ads", [])
            if ads:
                # Create a set of unique ads by md5
                unique_ads = {ad["md5"]: ad for ad in ads}.values()
                
                # Download each unique ad
                for ad in unique_ads:
                    if not self.download_interruption_track(ad["normalisedCampaignUrl"], ad["md5"]):
                        logger.error(f"Failed to download ad audio: {ad['md5']}")
                        return False

            self.interruptions_loaded = True
            logger.info("All interruption files loaded successfully")
            return True

        except Exception as e:
            logger.error(f"Error loading interruption files: {e}")
            return False

    def get_interruption_path(self, md5: str) -> str | None:
        """
        Get the path to a cached interruption file using the md5 as key
        
        Args:
            md5: The md5 of the interruption track
            
        Returns:
            str | None: Path to the cached file if it exists, None otherwise
        """
        try:
            cache_path = os.path.join(CACHE_DIR, md5)
            return cache_path if os.path.exists(cache_path) else None
            
        except Exception as e:
            logger.error(f"Error getting interruption path: {e}")
            return None