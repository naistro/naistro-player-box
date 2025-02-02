# app/player.py
import os
import requests
import vlc
import time
import yaml
import logging
from app.logger import setup_logger

with open("config/config.yaml", "r") as file:
    config = yaml.safe_load(file)

NORMALIZED_CDN = config["api"]["normalized_cdn"]
PUBLISHED_CDN = config["api"]["published_cdn"]

# Initialize logger
logger = setup_logger()

# Directory to store cached tracks
CACHE_DIR = "cache/tracks"

# Ensure cache directory exists
os.makedirs(CACHE_DIR, exist_ok=True)

class Player:
    def __init__(self):
        self.instance = vlc.Instance()
        self.player = self.instance.media_player_new()
        self.current_track_index = 0
        self.playlist = []

    def download_track(self, url, track_id, track_md5):
        """Download a track and save it to the cache directory."""
        try:
            track_path = os.path.join(CACHE_DIR, track_md5)
            if os.path.exists(track_path):
                logger.info(f"Track {track_id} already cached.")
                return track_path

            logger.info(f"Downloading track {track_id} from {url}...")
            response = requests.get(url, stream=True)
            response.raise_for_status()

            with open(track_path, "wb") as f:
                for chunk in response.iter_content(chunk_size=8192):
                    f.write(chunk)

            logger.info(f"Track {track_id} downloaded and cached.")
            return track_path

        except Exception as e:
            logger.error(f"Failed to download track {track_id}: {e}")
            return None

    def add_track_to_queue(self, track):
        """Add a track to the player queue."""
        try:
            track_md5 = track.get("md5")
            track_id = track.get("id")
            track_url = (f"{NORMALIZED_CDN}/{track.get('id')}" if track.get("type") == "Track"
                        else track.get("url"))
            logger.info(f"Add track to queue, md5, {track_md5} added to queue.")

            track_path = self.download_track(track_url, track_id, track_md5)

            if track_path:
                media = self.instance.media_new(track_path)
                self.player.set_media(media)
                self.playlist.append({"media": media, "track": track})  # Store track metadata
                logger.info(f"Track {track_id} added to queue.")
            else:
                logger.error(f"Failed to add track {track_id} to queue.")

        except Exception as e:
            logger.error(f"Error adding track to queue: {e}")

    def play_track_at_offset(self, track, offset):
        """Play a track from a specific offset."""
        try:
            # Set the media for the player
            self.player.set_media(track["media"])
            # Seek to the specified offset
            self.seek(offset)
            # Start playback
            self.player.play()
            logger.info(f"Playing track from offset: {offset} seconds.")
        except Exception as e:
            logger.error(f"Error playing track at offset: {e}")

    def play(self):
        """Start playing the playlist."""
        if not self.playlist:
            logger.error("No tracks in the playlist.")
            return

        logger.info("Starting playback...")
        self.player.play()

        # Monitor playback and load next tracks
        while True:
            time.sleep(1)
            if not self.player.is_playing():
                self.current_track_index += 1
                if self.current_track_index >= len(self.playlist):
                    logger.info("End of playlist.")
                    break

                # Get the next track and its metadata
                next_track = self.playlist[self.current_track_index]
                track_metadata = next_track["track"]

                # Check if the track should start from an offset
                if (track_metadata.get("adjustedDuration") != track_metadata.get("metadata", {}).get("runtime") and
                    (track_metadata.get("splitType") == "leftover" or track_metadata.get("metadata", {}).get("start"))):
                    offset = track_metadata.get("metadata", {}).get("start") or (
                        track_metadata.get("metadata", {}).get("runtime") - track_metadata.get("adjustedDuration")
                    )
                    if offset > 10:
                        self.play_track_at_offset(next_track, offset)
                    else:
                        self.play_track_at_offset(next_track, track_metadata.get("metadata", {}).get("runtime") - 10)
                else:
                    # Play the track normally
                    self.player.set_media(next_track["media"])
                    self.player.play()

    def stop(self):
        """Stop playback."""
        self.player.stop()
        logger.info("Playback stopped.")

    def seek(self, offset):
        """Seek to a specific position in the current track."""
        self.player.set_time(int(offset * 1000))  # Convert seconds to milliseconds
        logger.info(f"Seeked to {offset} seconds.")

    def skip_to_next(self):
        """Skip to the next track in the playlist."""
        self.current_track_index += 1
        if self.current_track_index < len(self.playlist):
            self.player.set_media(self.playlist[self.current_track_index]["media"])
            self.player.play()
            logger.info("Skipped to next track.")
        else:
            logger.info("No more tracks to skip.")

def start_player(playlist):
    """Start playing the playlist."""
    player = Player()
    for track in playlist[:10]:  # Load first 10 tracks
        player.add_track_to_queue(track)
    player.play()