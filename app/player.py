# app/player.py
import datetime
import os
import requests
import mpv
import time
import yaml
import logging
from app.interruption_manager import InterruptionManager
from app.volume_controller import VolumeController

logger = logging.getLogger("naistro-player")

with open("config/config.yaml", "r") as file:
    config = yaml.safe_load(file)

NORMALIZED_CDN = config["api"]["normalized_cdn"]
PUBLISHED_CDN = config["api"]["published_cdn"]

# Directory to store cached tracks
CACHE_DIR = "cache/tracks"
os.makedirs(CACHE_DIR, exist_ok=True)


class Player:
    def __init__(self):
        # Create main player instance for regular tracks
        self.main_player = mpv.MPV(input_default_bindings=True, input_vo_keyboard=True)
        self.interruption_player = mpv.MPV(input_default_bindings=True, input_vo_keyboard=True)
        
        # Register observers for the main player
        self.main_player.observe_property('playlist-pos', self.on_playlist_pos_changed)
        self.main_player.event_callback('end-file', self.on_end_file)

        # Tracking variables (keep existing ones)
        self.current_track_index = 0      # Current playing index (0-based)
        self.added_tracks_count = 0       # Number of tracks loaded into mpv's playlist
        self.playlist = []                # Full list of track metadata (populated from start_player)
        self.playlist_length = 0          # Total number of tracks
        self.location_offset = 0
        self.location_data = None
        self.volume = 100  # Default volume
                
        # Initialize interruption manager with both players
        self.volume_controller = VolumeController(self.interruption_player, self.main_player)
        self.interruption_manager = InterruptionManager(self.interruption_player, self.volume_controller)

    def on_playlist_pos_changed(self, name, value):
        """
        Called when the mpv property 'playlist-pos' changes.
        When a new file starts, update the current index, apply any offset adjustments,
        and preload more tracks.
        """
        # Skip if an interruption is playing
        if self.interruption_manager.current_interruption_type:
            logger.debug(f"Skipping playlist position change during {self.interruption_manager.current_interruption_type} interruption")
            return

        logger.info(f"Playlist position changed to: {value}")
        if value == -1:
            logger.info("No track is currently active.")
            return
        self.current_track_index = value
        try:
            if value < self.playlist_length:
                # Get the track metadata for the current position.
                track = self.playlist[value]
                self.play_track_at_offset(track, value)
                # Preload the next 5 tracks (if any)
                self.preload_next_tracks(5)
            else:
                logger.info("Playlist finished.")
        except Exception as e:
            logger.error(f"Error in on_playlist_pos_changed: {e}")

    def on_end_file(self, event):
        """
        Called when the current file has finished playing.
        mpv automatically advances the playlist.
        """
        logger.info(f"End of file reached. Event: {event}")

    def add_track_to_queue(self, track):
        """
        Download the track (if needed) and load it into mpv’s playlist.
        The first track is loaded with mode 'replace' so it starts immediately;
        subsequent tracks are appended.
        """
        try:
            track_md5 = track.get("md5")
            track_id = track.get("id")
            track_url = (f"{NORMALIZED_CDN}/{track.get('id')}"
                         if track.get("type") == "Track"
                         else track.get("url"))

            track_path = self.download_track(track_url, track_id, track_md5)
            if track_path:
                mode = "replace" if self.added_tracks_count == 0 else "append"
                self.main_player.loadfile(track_path, mode)  # Use main_player instead of player
                self.added_tracks_count += 1
                logger.info(f"Track {track_id} added to queue.")
            else:
                logger.error(f"Failed to add track {track_id} to queue.")
        except Exception as e:
            logger.error(f"Error adding track to queue: {e}")

    def preload_next_tracks(self, count):
        """
        Preload the next `count` tracks into the mpv playlist.
        This method looks at the provided playlist and loads any tracks that
        have not yet been added.
        """
        logger.info(f"Preloading next {count} tracks...")
        try:
            start_index = self.added_tracks_count
            end_index = start_index + count
            logger.info(f"Preloading tracks from index {start_index} to {end_index}...")
            for i in range(start_index, end_index):
                if i >= self.playlist_length:
                    break  # No more tracks available.
                track = self.playlist[i]
                self.add_track_to_queue(track)
        except Exception as e:
            logger.error(f"Error preloading next tracks: {e}")

    def download_track(self, url, track_id, track_md5):
        """
        Download a track from `url` and save it under the cache directory.
        If the track is already cached, return the cached file path.
        """
        try:
            track_path = os.path.join(CACHE_DIR, track_md5)
            if os.path.exists(track_path):
                logger.info(f"Track {track_id} already cached.")
                return track_path

            # logger.info(f"Downloading track {track_id} from {url}...")
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

    def play_track_at_offset(self, track, index):
        logger.info(f"Playing track with offset adjustment if needed: {track} at index {index}")

        try:
            # Ensure metadata and runtime are available
            metadata = track.get("metadata", {})
            runtime = int(metadata.get("runtime", 0))

            # Validate that we are playing the first track and it has a valid runtime
            if index == 0 and runtime > 0:
                # Get the current timestamp in Unix format
                current_time = datetime.datetime.now().timestamp()

                # Compute the offset based on the play time and location offset
                play_at = track.get("playAt", 0)  # Assuming Unix timestamp
                location_offset = self.location_offset * 2 * -1

                offset = int(current_time - (play_at - (location_offset * 2)))

                logger.info(f"runtime: {runtime}")

                is_valid_offset = runtime - offset

                logger.info(f"isValidOffset: {is_valid_offset}")
                logger.info(f"offset: {offset}")

                time.sleep(1)

                # If offset is significantly large (like 30 sec) and greater than 5 sec, seek to offset
                if is_valid_offset > 30 and offset > 5:
                    logger.info(f"Seeking to {offset} seconds.")
                    self.main_player.seek(offset, reference="absolute")
                else:
                    fallback_offset = max(runtime - 60, 0)
                    logger.info(f"Seeking to {fallback_offset} seconds instead.")
                    self.main_player.seek(fallback_offset, reference="absolute")

            else:
                logger.info("No offset adjustment needed for this track.")

        except Exception as e:
            logger.error(f"Error in play_track_at_offset: {e}")

    def set_volume(self, volume):
        """Set volume for main player"""
        try:
            volume = max(0, min(100, volume))
            self.volume = volume
            self.main_player.volume = volume
            logger.debug(f"Main player volume set to {volume}")
        except Exception as e:
            logger.error(f"Error setting volume: {e}")

    def play(self):
        try:
            if self.playlist_length == 0:
                logger.error("No tracks in the playlist.")
                return

            logger.info("Starting playback...")
            self.main_player.pause = False  # Use main_player
            self.main_player.volume = self.volume
        except Exception as e:
            logger.error(f"Error starting playback: {e}")
    
    def stop(self):
        """Stop both players."""
        try:
            # Check if player is in a state where it can be stopped
            if hasattr(self, 'main_player') and self.main_player:
                try:
                    # Try to pause first (which is safer if player isn't fully initialized)
                    self.main_player.pause = True
                    self.main_player.command('stop')
                except:
                    # Fallback for handling cleanup
                    pass
                        
                if hasattr(self, 'interruption_player') and self.interruption_player:
                    try:
                        self.interruption_player.pause = True
                        self.interruption_player.command('stop')
                    except:
                        pass

                logger.info("Player stopped. Returning to idle state.")
                
                # Reset state variables
                self.current_track_index = 0
                self.added_tracks_count = 0
                
        except Exception as e:
            logger.error(f"Error stopping players: {e}")
            # Continue execution despite errors

    def seek(self, offset):
        """Seek in the main player."""
        try:
            self.main_player.seek(offset, reference='absolute')
            logger.info(f"Seeked to {offset} seconds.")
        except Exception as e:
            logger.error(f"Error seeking: {e}")

    def skip_to_next(self):
        """Skip to next track in main player."""
        try:
            self.main_player.command("playlist-next")
            logger.info("Skipped to next track.")
        except Exception as e:
            logger.error(f"Error skipping to next track: {e}")

    def _setup_location(self):
        """Setup player with location data"""
        try:            
            # Set initial volume from location data (0-10 range)
            try:
                location_volume = self.location_data['volume']
                if isinstance(location_volume, (int, float)) and 0 <= location_volume <= 10:
                    # Convert to MPV's 0-100 range
                    mpv_volume = location_volume * 10
                    self.volume = mpv_volume
                    logger.info(f"Set initial volume to {location_volume} (MPV: {mpv_volume})")
                else:
                    logger.warning(f"Invalid location volume {location_volume}, using default 10.0")
                    self.volume = 100
            except (KeyError, TypeError):
                logger.warning("Location volume not found or invalid, using default 10.0")
                self.volume = 100
            
            if "interruptions" in self.location_data:
                self.interruption_manager.setup_interruptions(self.location_data, self.location_offset)
            
            # Load the first 10 tracks into mpv.
            for track in self.playlist[:10]:
                self.add_track_to_queue(track)
                
            logger.info(f"Location setup complete: {len(self.playlist)} tracks, offset {self.location_offset}s")
            
        except Exception as e:
            logger.error(f"Error setting up location: {e}", exc_info=True)
            raise

    def start_playback_by_guid(self, guid):
        """
        Start playback for a location with the specified GUID
        
        Args:
            guid: GUID of the location to play
        """
        try:
            # Find the location with the matching GUID
            location = self._find_location_by_guid(guid)
            
            if location:
                logger.info(f"Starting playback for location: {location.get('name')}")
                # Save the current player state
                self.playlist = []
                self.playlist_length = 0
                self.current_track_index = 0
                self.added_tracks_count = 0
                
                # Fetch playlist for this location
                from app.api import fetch_playlist, fetch_location
                location_id = location.get("guid")
                playlistData = fetch_playlist(location_id)
                locationData = fetch_location(location_id)
                
                # Validate playlist data
                if not playlistData.get("events"):
                    logger.error("No tracks found in the playlist")
                    return
                    
                # Update player state
                self.playlist = playlistData["events"]
                self.playlist_length = len(self.playlist)
                self.location_offset = playlistData["locationOffset"]
                self.location_data = locationData
                
                # Set up location and start playback
                self._setup_location()
                self.play()
        except Exception as e:
            logger.error(f"Error starting playback by GUID: {e}", exc_info=True)
        
    def _find_location_by_guid(self, guid):
        """
        Find a location by its GUID in the available locations
        
        Args:
            guid: GUID of the location to find
            
        Returns:
            Location data or None if not found
        """
        try:
            # Fetch all locations
            from app.api import fetch_locations
            locations = fetch_locations()
            
            if not locations:
                logger.error("No locations available")
                return None
                
            # Find the location with the matching GUID
            for location in locations:
                if location.get('guid') == guid:
                    return location
                    
            logger.warning(f"Location with GUID {guid} not found")
            return None
        except Exception as e:
            logger.error(f"Error finding location by GUID: {e}", exc_info=True)
            return None


def start_player(playlist, locationOffset, locationData):
    """
    Initialize the player, load the initial set of tracks, and start playback.
    The full playlist (a list of track metadata dictionaries) is stored in the player,
    and the first 10 tracks are immediately added to mpv's playlist.
    """
    player = Player()
    # Store the complete playlist and its length.
    player.playlist = playlist
    player.playlist_length = len(playlist)
    player.location_offset = locationOffset
    player.location_data = locationData

    logger.info(f"Location offset: {locationOffset} seconds")

    player._setup_location()

    player.play()

    try:
        # Keep the program alive as long as there are tracks playing.
        while player.current_track_index < player.playlist_length:
            time.sleep(1)
    except KeyboardInterrupt:
        logger.info("Playback stopped by user.")
    finally:
        player.stop()
