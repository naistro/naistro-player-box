import logging
from datetime import datetime, timedelta, timezone
from threading import Timer
from app.interruption_storage import InterruptionStorage
from app.volume_controller import VolumeController

logger = logging.getLogger("naistro-player")

class InterruptionManager:
    def __init__(self, interruption_player, volume_controller):
        """Initialize interruption manager with dedicated player"""
        self.player = interruption_player
        self.volume_controller = volume_controller
        self.next_prayer = None
        self.next_campaign = None
        self.prayer_timer = None
        self.campaign_timer = None
        self.is_in_silence = False
        self.location_data = None
        self.location_offset = None
        self.storage = InterruptionStorage()
        self.current_interruption_type = None

    def setup_interruptions(self, location_data, location_offset):
        """Set up all interruptions from location data"""
        try:
            self.location_data = location_data
            self.location_offset = location_offset
            
            logger.info("Setting up interruptions")
            logger.debug(f"Location offset: {location_offset} seconds")
            
            interruptions = location_data.get('interruptions', {})
            
            # Setup prayer times
            self._setup_next_prayer(interruptions)
            
            # Setup campaigns
            self._setup_next_campaign(interruptions)
            
        except Exception as e:
            logger.error(f"Error setting up interruptions: {e}", exc_info=True)

    def _setup_next_prayer(self, interruptions):
        """Setup next prayer time"""
        logger.debug(f"Prayer times setup")
        try:
            prayers = interruptions.get('prayerTimes', [])
            prayer_config = interruptions.get('config', {}).get('prayerTimes')
            if not prayers:
                logger.debug("No prayer times available")
                return

            # Get current time as timezone-aware datetime
            now = datetime.now(timezone.utc)
            
            # Sort prayers by start time
            sorted_prayers = sorted(prayers, key=lambda x: datetime.fromisoformat(x['start']))
            
            # Find next prayer time
            for prayer in sorted_prayers:
                try:         
                    # Parse start time as UTC
                    start_time = datetime.fromisoformat(prayer['start'].replace('Z', '+00:00'))
                    if not start_time.tzinfo:
                        start_time = start_time.replace(tzinfo=timezone.utc)
                    
                    # Apply location offset
                    timezone_adjusted_start = start_time - timedelta(seconds=self.location_offset * -1)
                    
                    if now < timezone_adjusted_start:
                        next_prayer = {
                            'type': 'prayer',
                            'title': prayer.get('title', 'Untitled Prayer'),
                            'md5': prayer_config['md5'],
                            'start': timezone_adjusted_start
                        }
                        
                        # Calculate delay until prayer time
                        delay_seconds = (timezone_adjusted_start - now).total_seconds()
                        
                        # Schedule the prayer
                        self._schedule_prayer(next_prayer)
                        logger.info(f"Next prayer {next_prayer['title']} scheduled for {next_prayer['start'].isoformat()} (in {delay_seconds:.1f}s)")
                        return
                        
                except (KeyError, ValueError) as e:
                    logger.error(f"Invalid prayer data: {e}", exc_info=True)
                    logger.debug(f"Problem prayer data: {prayer}")
                    continue

            logger.info("No upcoming prayer times found")
                
        except Exception as e:
            logger.error(f"Error setting up next prayer: {e}", exc_info=True)

    def _setup_next_campaign(self, interruptions):
        """Setup next campaign"""
        try:
            campaigns = interruptions.get('ads', [])
            if not campaigns:
                logger.debug("No campaigns available")
                return
                
            # Get current time as timezone-aware datetime
            now = datetime.now(timezone.utc)
            
            # Sort campaigns by start time
            sorted_campaigns = sorted(campaigns, key=lambda x: datetime.fromisoformat(x['start']))
            
            # Find next campaign
            for campaign in sorted_campaigns:
                try:
                    # Parse start time as UTC
                    start_time = datetime.fromisoformat(campaign['start'].replace('Z', '+00:00'))
                    if not start_time.tzinfo:
                        start_time = start_time.replace(tzinfo=timezone.utc)
                    
                    # Apply location offset
                    timezone_adjusted_start = start_time - timedelta(seconds=self.location_offset * -1)
                    
                    if now < timezone_adjusted_start:
                        next_campaign = {
                            'type': 'campaign',
                            'title': campaign.get('title', 'Untitled Campaign'),
                            'md5': campaign['md5'],
                            'url': campaign['normalisedCampaignUrl'],
                            'exact_time': campaign.get('exactTime', False),
                            'start': timezone_adjusted_start
                        }
                        
                        # Calculate delay until campaign start
                        delay_seconds = (timezone_adjusted_start - now).total_seconds()
                        
                        # Schedule the campaign
                        self._schedule_campaign(next_campaign, delay_seconds)
                        logger.info(f"Next campaign {next_campaign['title']} scheduled for {next_campaign['start'].isoformat()} (in {delay_seconds:.1f}s)")
                        return
                        
                except (KeyError, ValueError) as e:
                    logger.error(f"Invalid campaign data: {e}", exc_info=True)
                    logger.debug(f"Problem campaign data: {campaign}")
                    continue
                    
            logger.info("No upcoming campaigns found")
                
        except Exception as e:
            logger.error(f"Error setting up next campaign: {e}", exc_info=True)

    def _schedule_campaign(self, campaign, delay_seconds):
        """Schedule the campaign"""
        try:
            # Start fade out 5 seconds before campaign time
            fade_start = datetime.now(timezone.utc) + timedelta(seconds=delay_seconds - 5)
            
            # If exactTime is true, don't use minimum delay
            time_until_fade = (fade_start - datetime.now(timezone.utc)).total_seconds()
            next_delay = time_until_fade if campaign['exact_time'] else max(time_until_fade, 2)
            
            logger.debug(f"Campaign: {campaign['title']}")
            logger.debug(f"  Fade start: {fade_start.isoformat()}")
            logger.debug(f"  Time until fade: {time_until_fade:.1f}s")
            logger.debug(f"  Final delay: {next_delay:.1f}s")
            logger.debug(f"  URL: {campaign['url']}")
            
            # Cancel existing timer if any
            if self.campaign_timer:
                self.campaign_timer.cancel()
                logger.debug("Cancelled existing campaign timer")
            
            # Store next campaign
            self.next_campaign = campaign
            
            # Schedule the campaign
            self.campaign_timer = Timer(
                next_delay,
                lambda: self._check_and_play_campaign(campaign)
            )
            self.campaign_timer.start()
            
            logger.info(f"Campaign scheduled: {campaign['title']} (in {delay_seconds:.1f} seconds)")
            
        except Exception as e:
            logger.error(f"Error scheduling campaign: {e}", exc_info=True)

    def _schedule_prayer(self, prayer):
        """Schedule the prayer time"""
        try:
            now = datetime.now(timezone.utc)
            
            # Calculate delay and start fade 5 seconds before prayer
            delay_seconds = (prayer['start'] - now).total_seconds()
            fade_start = prayer['start'] - timedelta(seconds=5)
            time_until_fade = (fade_start - now).total_seconds()
            
            logger.debug(f"Prayer: {prayer['title']}")
            logger.debug(f"  Start time: {prayer['start'].isoformat()}")
            logger.debug(f"  Fade start: {fade_start.isoformat()}")
            logger.debug(f"  Time until fade: {time_until_fade:.1f}s")
            
            # Cancel existing timer if any
            if self.prayer_timer:
                self.prayer_timer.cancel()
                logger.debug("Cancelled existing prayer timer")
            
            # Store next prayer
            self.next_prayer = prayer
            
            # Schedule the prayer
            self.prayer_timer = Timer(
                time_until_fade,
                lambda: self._play_interruption(prayer)
            )
            self.prayer_timer.start()
            
            logger.info(f"Prayer scheduled: {prayer['title']} (in {delay_seconds:.1f} seconds)")
            
        except Exception as e:
            logger.error(f"Error scheduling prayer time: {e}", exc_info=True)

    def _check_and_play_campaign(self, campaign):
        """Check if we can play campaign and start playback"""
        try:
            # Check if prayer is active
            if self.current_interruption_type == 'prayer':
                logger.info("Prayer is active, cleaning up and skipping campaign")
                self.next_campaign = None
                if self.campaign_timer:
                    self.campaign_timer.cancel()
                    self.campaign_timer = None
                    
                # Schedule next campaign
                if self.location_data:
                    self._setup_next_campaign(self.location_data.get('interruptions', {}))
                return
                
            # Check if a prayer time is about to start
            if self.next_prayer:
                now = datetime.now(timezone.utc)
                campaign_duration_seconds = 30  # Default duration for campaigns
                campaign_end = now + timedelta(seconds=campaign_duration_seconds)
                
                # Skip if campaign would overlap with prayer time
                if now < self.next_prayer['start'] < campaign_end:
                    logger.info(f"Skipping campaign due to upcoming prayer at {self.next_prayer['start'].isoformat()}")
                    return
            
            # Play the campaign
            self._play_interruption(campaign)

        except Exception as e:
            logger.error(f"Error checking and playing campaign: {e}", exc_info=True)

    def _play_interruption(self, interruption):
        """Play an interruption with proper volume transitions"""
        try:
            if self.current_interruption_type == 'prayer':
                logger.warning("Prayer is active, skipping any other interruption")
                return
                
            # Get location volume (0-10 range)
            try:
                location_volume = float(self.location_data['volume'])
                if not 0 <= location_volume <= 10:
                    raise ValueError("Volume out of range")
            except (KeyError, ValueError, TypeError):
                logger.warning("Invalid location volume, using default 10.0")
                location_volume = 10.0
            
            # Log interruption details
            logger.info(f"Starting {interruption['type']} interruption: {interruption.get('title', 'Untitled')} at {datetime.now(timezone.utc).isoformat()}")
            
            # Play from cache
            audio_file = self.storage.get_interruption_path(interruption['md5'])
            if not audio_file:
                logger.error(f"Could not find cached file for {interruption['type']} interruption")
                self._handle_interruption_complete(interruption['type'])
                return
                    
            # Play from cache
            self.volume_controller.play_interruption(
                audio_file,
                location_volume,
                lambda: self._handle_interruption_complete(interruption['type'])
            )
            
            # Set interruption state
            self.current_interruption_type = interruption['type']
            
        except Exception as e:
            logger.error(f"Error playing interruption: {e}", exc_info=True)
            self._handle_interruption_complete(interruption['type'])

    def _handle_interruption_complete(self, interruption_type):
        """Handle interruption completion"""
        try:
            logger.info(f"Handling completion of {interruption_type} interruption")
            
            # Reset state based on type
            if interruption_type == 'campaign':
                self.next_campaign = None
                if self.campaign_timer:
                    self.campaign_timer.cancel()
                    self.campaign_timer = None
                    
                # Schedule next campaign
                if self.location_data:
                    self._setup_next_campaign(self.location_data.get('interruptions', {}))
                    
            elif interruption_type == 'prayer':
                self.next_prayer = None
                if self.prayer_timer:
                    self.prayer_timer.cancel()
                    self.prayer_timer = None
                    
                # Schedule next prayer
                if self.location_data:
                    self._setup_next_prayer(self.location_data.get('interruptions', {}))
            
            # Reset silence state
            self.is_in_silence = False
            self.current_interruption_type = None
            
            # Ensure main player is resumed
            if self.volume_controller.main_player and self.volume_controller.main_player.pause:
                self.volume_controller.main_player.pause = False
                logger.info("Resumed main player after interruption.")
            
            logger.info(f"{interruption_type} interruption completed")
            
        except Exception as e:
            logger.error(f"Error handling interruption completion: {e}", exc_info=True)
            # Ensure we reset silence state even if there's an error
            self.is_in_silence = False
            self.current_interruption_type = None        

    
    def trigger_birthday(self):
        """Manually trigger birthday interruption"""
        try:
            if not self.location_data:
                logger.error("No location data available")
                return False
                
            if not self.location_data.get("isBdayEnabled"):
                logger.error("Birthday interruptions not enabled")
                return False

            # Don't interrupt prayer times
            if self.current_interruption_type == 'prayer':
                logger.info("Cannot trigger birthday during prayer time")
                return False

            birthday = {
                'type': 'birthday',
                'md5': self.location_data['bDayTrackMd5']
            }

            self._play_interruption(birthday)
            return True

        except Exception as e:
            logger.error(f"Error triggering birthday interruption: {e}", exc_info=True)
            return False