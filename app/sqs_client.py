# app/sqs_client.py
import boto3
import json
import logging
import threading
import time
import yaml
from botocore.exceptions import ClientError

logger = logging.getLogger("naistro-player")

try:
    with open("config/config.yaml", "r") as file:
        config = yaml.safe_load(file)
    with open("config/auth.yaml", "r") as file:
        aws_config = yaml.safe_load(file)
    logger.info("Configuration loaded successfully.")
except Exception as e:
    logger.error(f"Failed to load configuration: {e}")
    raise

class SQSClient:
    """SQS client for player box remote control"""
    
    def __init__(self, player, user_id):
        """
        Initialize SQS client
        
        Args:
            player: Player instance to control
            user_id: User ID to filter messages by
        """
        self.player = player
        self.user_id = user_id
        self.queue_url = config["api"]["sqs_url"]
        self.sqs = boto3.client(
            'sqs',
            region_name="eu-west-1",
            aws_access_key_id=aws_config["aws"]["access_key_id"],
            aws_secret_access_key=aws_config["aws"]["secret_access_key"]
        )
        self.running = False
        self.polling_thread = None
        
    def start(self):
        """Start polling SQS queue"""
        if self.polling_thread and self.polling_thread.is_alive():
            logger.info("SQS client already running")
            return
            
        self.running = True
        self.polling_thread = threading.Thread(target=self._poll_queue)
        self.polling_thread.daemon = True
        self.polling_thread.start()
        logger.info(f"SQS client started for user ID: {self.user_id}")
        
    def stop(self):
        """Stop polling SQS queue"""
        self.running = False
        if self.polling_thread:
            self.polling_thread.join(timeout=2)
        logger.info("SQS client stopped")
        
    def _poll_queue(self):
        """Poll SQS queue for messages"""
        retry_delay = 1
        max_retry_delay = 20
        
        while self.running:
            try:
                # Use MessageAttribute filtering to only retrieve messages for this userId
                response = self.sqs.receive_message(
                    QueueUrl=self.queue_url,
                    MaxNumberOfMessages=1,
                    WaitTimeSeconds=20,
                    MessageAttributeNames=['userId'],
                    AttributeNames=['All']
                )
            
                messages = response.get('Messages', [])
                if messages:
                    logger.info(f"Received {len(messages)} messages from SQS")
                    for message in messages:
                        # Check if this message has the correct userId attribute
                        message_attributes = message.get('MessageAttributes', {})
                        user_id_attr = message_attributes.get('userId', {})

                        logger.info(f"Processing message: {message}")
                        logger.debug(f"Message userId attribute: {user_id_attr.get('StringValue')}")
                    
                    if user_id_attr.get('StringValue') == self.user_id:
                        self._process_message(message)
                        self._delete_message(message)
                    else:
                        logger.debug(f"Ignoring message with incorrect userId attribute: {user_id_attr.get('StringValue')}")
                
                # Reset retry delay on success
                retry_delay = 1
                
            except ClientError as e:
                logger.error(f"SQS client error: {e}", exc_info=True)
                # Implement exponential backoff with jitter
                time.sleep(retry_delay)
                retry_delay = min(retry_delay * 2, max_retry_delay)
                
    def _process_message(self, message):
        """
        Process SQS message
        
        Args:
            message: SQS message to process
        """
        try:
            # Parse message body
            body = json.loads(message.get('Body', '{}'))
            
            # Extract control command and location GUID
            control = body.get('control')
            location_guid = body.get('locationGuid')
            
            logger.info(f"Processing command: {control}, location: {location_guid}")
            
            # Execute command
            if control == "play" and location_guid:
                self.player.start_playback_by_guid(location_guid)
            elif control == "stop":
                self.player.stop()
            else:
                logger.warning(f"Unknown command: {control}")
                
        except json.JSONDecodeError:
            logger.error("Invalid JSON in message body", exc_info=True)
        except Exception as e:
            logger.error(f"Error processing message: {e}", exc_info=True)
            
    def _delete_message(self, message):
        """
        Delete message from SQS queue
        
        Args:
            message: SQS message to delete
        """
        try:
            self.sqs.delete_message(
                QueueUrl=self.queue_url,
                ReceiptHandle=message['ReceiptHandle']
            )
            logger.debug("Message deleted from queue")
        except ClientError as e:
            logger.error(f"Error deleting message: {e}", exc_info=True)