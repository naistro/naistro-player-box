# app/player.py
import os
import requests
import mpv
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
os.makedirs(CACHE_DIR, exist_ok=True)


class Player:
    def __init__(self):
        # Create an mpv player instance with default input bindings.
        self.player = mpv.MPV(input_default_bindings=True, input_vo_keyboard=True)
        
        # Register an observer for the playlist position.
        # This callback is invoked whenever the current file changes.
        self.player.observe_property('playlist-pos', self.on_playlist_pos_changed)
        # Also attach an event callback for when a file finishes.
        self.player.event_callback('end-file', self.on_end_file)

        # Tracking variables
        self.current_track_index = 0      # Current playing index (0-based)
        self.added_tracks_count = 0       # Number of tracks loaded into mpv's playlist
        self.playlist = []                # Full list of track metadata (populated from start_player)
        self.playlist_length = 0          # Total number of tracks

    def on_playlist_pos_changed(self, name, value):
        """
        Called when the mpv property 'playlist-pos' changes.
        When a new file starts, update the current index, apply any offset adjustments,
        and preload more tracks.
        """
        logger.info(f"Playlist position changed to: {value}")
        if value == -1:
            logger.info("No track is currently active.")
            return
        self.current_track_index = value
        try:
            if value < self.playlist_length:
                # Get the track metadata for the current position.
                track = self.playlist[value]
                self.play_track_at_offset(track)
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
            # Determine the URL based on track type.
            track_url = (f"{NORMALIZED_CDN}/{track.get('id')}"
                         if track.get("type") == "Track"
                         else track.get("url"))
            # logger.info(f"Adding track to queue, md5: {track_md5} for track {track_id}.")

            # Download (or get cached) track file.
            track_path = self.download_track(track_url, track_id, track_md5)
            if track_path:
                mode = "replace" if self.added_tracks_count == 0 else "append"
                # mpv.loadfile will add the file to its internal playlist.
                self.player.loadfile(track_path, mode)
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

    def play_track_at_offset(self, track):
        """
        Check track metadata for any start offset adjustments and apply them.
        This is similar to your VLC logic where, if the adjusted duration differs
        from the full runtime (or if playing a 'leftover' split), we seek to the proper offset.
        """
        logger.info(f"Playing track with offset adjustment if needed: {track}")
        try:
            adjusted_duration = int(track.get("adjustedDuration"))
            metadata = track.get("metadata", {})
            runtime = int(metadata.get("runtime"))

            # If the track has an offset (by split or explicit start time), adjust playback.
            if adjusted_duration != runtime and (track.get("splitType") == "leftover" or metadata.get("start")):
                offset = int(metadata.get("start")) or (runtime - adjusted_duration)
                # Give mpv a brief moment to load the file.
                time.sleep(0.5)
                if offset > 10:
                    logger.info(f"Setting playback offset to {offset} seconds.")
                    logger.info(f"Adjusted duration: {runtime - offset}, Runtime: {runtime}")
                    self.player.time = 300
                else:
                    logger.info(f"Setting playback offset in else case to {runtime - 10} seconds.")
                    logger.info(f"Adjusted duration in else case: {10}, Runtime: {runtime}")
                    self.player.time = runtime - 10
            else:
                logger.info("No offset adjustment needed for this track.")
        except Exception as e:
            logger.error(f"Error in play_track_at_offset: {e}")

    def play(self):
        """
        Start playback.
        (mpv will start playing as soon as the first file is loaded;
        here we make sure that playback is not paused.)
        """
        try:
            if self.playlist_length == 0:
                logger.error("No tracks in the playlist.")
                return

            logger.info("Starting playback...")
            self.player.pause = False  # Ensure the player is not paused.
        except Exception as e:
            logger.error(f"Error starting playback: {e}")

    def stop(self):
        """Stop playback by quitting mpv."""
        try:
            self.player.quit()
            logger.info("Playback stopped.")
        except Exception as e:
            logger.error(f"Error stopping playback: {e}")

    def seek(self, offset):
        """Seek to a specific position (in seconds) in the current track."""
        try:
            self.player.seek(offset, reference='absolute')
            logger.info(f"Seeked to {offset} seconds.")
        except Exception as e:
            logger.error(f"Error seeking: {e}")

    def skip_to_next(self):
        """Skip to the next track in the playlist."""
        try:
            self.player.command("playlist-next")
            logger.info("Skipped to next track.")
        except Exception as e:
            logger.error(f"Error skipping to next track: {e}")


def start_player(playlist):
    """
    Initialize the player, load the initial set of tracks, and start playback.
    The full playlist (a list of track metadata dictionaries) is stored in the player,
    and the first 10 tracks are immediately added to mpv's playlist.
    """
    player = Player()
    # Store the complete playlist and its length.
    player.playlist = playlist
    player.playlist_length = len(playlist)

    # Load the first 10 tracks into mpv.
    for track in playlist[:10]:
        player.add_track_to_queue(track)

    player.play()

    try:
        # Keep the program alive as long as there are tracks playing.
        while player.current_track_index < player.playlist_length:
            time.sleep(1)
    except KeyboardInterrupt:
        logger.info("Playback stopped by user.")
    finally:
        player.stop()
