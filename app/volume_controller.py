"""Volume control functionality for audio transitions"""
import logging
import time
from threading import Timer
import mpv

logger = logging.getLogger("naistro-player")

class VolumeController:
    def __init__(self, interruption_player: mpv.MPV, main_player=None):
        self.interruption_player: mpv.MPV = interruption_player
        self.main_player: mpv.MPV = main_player
        self.fade_timer = None
        self.completion_callback = None
        self.target_volume = 0
        self.main_player_original_volume = 100  # Store the original volume of the main player
        self.log_service = None  # Will be set when player connects to websocket

    def set_main_player(self, main_player):
        """Set the main player instance"""
        if main_player is None:
            logger.error("main_player is None!")
        self.main_player = main_player
        # Store the original volume of the main player
        if self.main_player:
            self.main_player_original_volume = self.main_player.volume

    def set_log_service(self, log_service):
        """Set the log service for state updates"""
        self.log_service = log_service

    def play_interruption(self, audio_file, location_volume, completion_callback=None):
        """Play interruption with simple fade-out and fade-in"""
        try:
            # Input validation
            if not audio_file or not isinstance(audio_file, str):
                raise ValueError("Invalid audio file path")
            if not isinstance(location_volume, (int, float)):
                raise ValueError("Invalid location volume")

            # Convert location volume (0-10) to MPV volume (0-100)
            self.target_volume = min(max(float(location_volume) * 10, 0), 100)

            # Fade out the main player volume before starting the interruption
            self._fade_volume(self.main_player_original_volume, 0, 5000, callback=lambda: self._start_interruption(audio_file, completion_callback))

        except Exception as e:
            logger.error(f"Error playing interruption: {e}", exc_info=True)
            if completion_callback:
                completion_callback()

    def _start_interruption(self, audio_file, completion_callback):
        """Start the interruption after fading out the main player"""
        try:
            # Set interruption volume
            self.interruption_player.volume = self.target_volume

            # Load and start playing the interruption
            self.interruption_player.loadfile(audio_file, "replace")
            logger.info(f"Started playing interruption: {audio_file}")

            # Make sure the main player is muted if for some reason it didn't fade out
            if self.main_player:
                self.main_player.volume = 0
                if self.log_service:
                    self.log_service.set_player_state("muted")

            # Wait for the file to load and initialize
            time.sleep(1)  # Add a short delay to allow file initialization

            # Log the duration of the interruption file
            try:
                duration = self.interruption_player.duration
                logger.info(f"Interruption file duration: {duration} seconds")
            except Exception as e:
                logger.error(f"Error getting file duration: {e}", exc_info=True)

            # Set completion callback
            self.completion_callback = completion_callback

            # Schedule fade-out based on file duration
            if duration:
                logger.info(f"Scheduling fade-out in {duration} seconds")
                self.fade_timer = Timer(duration, self.on_end_file)
                self.fade_timer.start()

        except Exception as e:
            logger.error(f"Error starting interruption: {e}", exc_info=True)
            if completion_callback:
                completion_callback()

    def on_end_file(self):
        """Handler for the end of the interruption"""
        logger.info("Interruption completed, starting fade in.")
        self._fade_volume(0, self.main_player_original_volume, 5000, callback=self.completion_callback)

    def _fade_volume(self, start_volume, end_volume, duration_ms, callback=None):
        """
        Fade volume smoothly between start and end values.
        For fade-out: Fade out main player before interruption
        For fade-in: Fade in main player after interruption
        """
        try:
            # Cancel any existing fade
            if self.fade_timer:
                self.fade_timer.cancel()
                self.fade_timer = None

            # Input validation
            start_volume = min(max(float(start_volume), 0), 100)
            end_volume = min(max(float(end_volume), 0), 100)
            duration_ms = max(float(duration_ms), 100)  # Minimum 100ms fade

            steps = 30  # Number of steps for smooth transition
            step_time = duration_ms / (steps * 1000)  # Convert to seconds
            volume_step = (end_volume - start_volume) / steps

            def do_fade(current_step=0):
                if current_step > steps:
                    # Fade completed
                    # If volume is 0, update player state to muted
                    if self.main_player and self.main_player.volume == 0 and self.log_service:
                        self.log_service.set_player_state("muted")
                        
                    if callback:
                        try:
                            logger.info("Fade completed. Executing callback...")
                            callback()
                        except Exception as e:
                            logger.error(f"Error in callback: {e}", exc_info=True)
                    return

                try:
                    # Calculate current volume
                    current_volume = start_volume + (volume_step * current_step)
                    current_volume = min(max(current_volume, 0), 100)

                    # Set main player volume
                    if self.main_player:
                        self.main_player.volume = current_volume
                        logger.debug(f"Fade step {current_step}/{steps}: main_player volume={current_volume:.1f}")
                        
                        # If this is the last step and volume is 0, update player state
                        if current_step == steps and current_volume == 0 and self.log_service:
                            self.log_service.set_player_state("muted")

                    # Schedule next step
                    self.fade_timer = Timer(step_time, lambda: do_fade(current_step + 1))
                    self.fade_timer.start()

                except Exception as e:
                    logger.error(f"Error in fade step {current_step}: {e}", exc_info=True)
                    if callback:
                        try:
                            logger.error("Fade failed. Executing callback...")
                            callback()
                        except Exception as cb_error:
                            logger.error(f"Error in callback: {cb_error}", exc_info=True)

            # Start the fade
            do_fade()

        except Exception as e:
            logger.error(f"Error starting volume fade: {e}", exc_info=True)
            if callback:
                try:
                    logger.error("Fade failed. Executing callback...")
                    callback()
                except Exception as cb_error:
                    logger.error(f"Error in callback: {cb_error}", exc_info=True)