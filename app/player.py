# app/player.py
import os
import requests
import vlc
import time
import yaml
import logging

logger = logging.getLogger("naistro-player")

with open("config/config.yaml", "r") as file:
    config = yaml.safe_load(file)

NORMALIZED_CDN = config["api"]["normalized_cdn"]
PUBLISHED_CDN = config["api"]["published_cdn"]

# Directory to store cached tracks
CACHE_DIR = "cache/tracks"

# Ensure cache directory exists
os.makedirs(CACHE_DIR, exist_ok=True)

class Player:
    def __init__(self):
        self.instance = vlc.Instance()
        self.media_list = self.instance.media_list_new()  # Create a MediaList
        self.media_list_player = self.instance.media_list_player_new()  # Create a MediaListPlayer
        self.media_list_player.set_media_list(self.media_list)  # Set the MediaList

        # Track the length of the MediaList manually
        self.media_list_length = 0

        # Attach event listeners
        self.event_manager = self.media_list_player.get_media_player().event_manager()
        self.event_manager.event_attach(
            vlc.EventType.MediaPlayerPlaying,
            self.on_media_player_playing
        )
        self.event_manager.event_attach(
            vlc.EventType.MediaPlayerEndReached,
            self.on_media_player_end_reached
        )

        self.current_track_index = 0
        self.playlist_length = 0
        self.playlist = []  # Store track metadata

    def on_media_player_playing(self, event):
        """Callback when playback starts."""
        try:
            logger.info("Playback started. The event is: %s" % event)
            track = self.playlist[self.current_track_index]
            self.play_track_at_offset(track)

            # Preload the next 5 tracks
            self.preload_next_tracks(5)
        except Exception as e:
            logger.error(f"Error in on_media_player_playing media: {e}")

    def on_media_player_end_reached(self, event):
        """Callback when playback ends."""
        try:
            logger.info("Playback ended. The event is: %s" % event)
            self.current_track_index += 1
            if self.current_track_index < self.playlist_length:
                logger.info(f"Advancing to next track: {self.current_track_index}")
                self.media_list_player.play_item_at_index(self.current_track_index)
            else:
                logger.info("Playlist finished.")
        except Exception as e:
            logger.error(f"Error in on_media_player_end_reached: {e}")

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
                self.media_list.add_media(media)  # Add media to the MediaList
                self.media_list_length += 1  # Update the MediaList length
                self.playlist.append({"media": media, "track": track})  # Store track metadata
                self.playlist_length += 1
                logger.info(f"Track {track_id} added to queue.")
            else:
                logger.error(f"Failed to add track {track_id} to queue.")

        except Exception as e:
            logger.error(f"Error adding track to queue: {e}")

    def preload_next_tracks(self, count):
        """Download and add the next `count` tracks to the playlist."""
        try:
            # Start from the last track in the player queue
            start_index = self.media_list_length
            end_index = min(start_index + count, len(self.playlist))

            for i in range(start_index, end_index):
                if i >= len(self.playlist):
                    break  # No more tracks to preload

                track = self.playlist[i]
                track_md5 = track.get("md5")
                track_id = track.get("id")
                track_url = (f"{NORMALIZED_CDN}/{track.get('id')}" if track.get("type") == "Track"
                            else track.get("url"))

                # Download the track if not already cached
                track_path = self.download_track(track_url, track_id, track_md5)

                if track_path:
                    media = self.instance.media_new(track_path)
                    self.media_list.add_media(media)  # Add media to the MediaList
                    self.media_list_length += 1  # Update the MediaList length
                    logger.info(f"Preloaded track {track_id} into the playlist.")
                else:
                    logger.error(f"Failed to preload track {track_id}.")

        except Exception as e:
            logger.error(f"Error preloading next tracks: {e}")

    # Other methods (download_track, play_track_at_offset, play, stop, seek, skip_to_next) remain unchanged
def start_player(playlist):
    """Start playing the playlist."""
    player = Player()
    for track in playlist[:10]:  # Load first 10 tracks
        player.add_track_to_queue(track)
    player.play()    
    
    try:
        while player.current_track_index < player.playlist_length:
            time.sleep(1)
    except KeyboardInterrupt:
        logger.info("Playback stopped by user.")
    finally:
        player.stop()