# app/auth.py
import boto3
import yaml
import os
from botocore.exceptions import BotoCoreError, ClientError
from app.logger import setup_logger

# Load configuration
logger = setup_logger()
logger.info("Loading configuration from auth.yaml...")

try:
    with open("config/auth.yaml", "r") as file:
        config = yaml.safe_load(file)
    logger.info("Configuration loaded successfully.")
except Exception as e:
    logger.error(f"Failed to load configuration: {e}")
    raise

TOKEN_FILE = "config/token.txt"

USER_POOL_ID = config["aws_cognito"]["user_pool_id"]
CLIENT_ID = config["aws_cognito"]["client_id"]
REGION = config["aws_cognito"]["region"]
AUTH_URL = config["aws_cognito"]["auth_url"]
USERNAME = config["credentials"]["username"]
PASSWORD = config["credentials"]["password"]

def get_auth_token():
    """Authenticate with AWS Cognito and return the token"""
    logger.info("Attempting to authenticate with AWS Cognito...")

    try:
        # Create Cognito Identity Provider client
        logger.debug("Creating Cognito Identity Provider client...")
        client = boto3.client("cognito-idp", region_name=REGION)

        # Authenticate user
        logger.debug(f"Authenticating user: {USERNAME}")
        response = client.initiate_auth(
            AuthFlow="USER_PASSWORD_AUTH",
            AuthParameters={
                "USERNAME": USERNAME,
                "PASSWORD": PASSWORD
            },
            ClientId=CLIENT_ID
        )

        # Extract tokens from response
        id_token = response["AuthenticationResult"]["IdToken"]
        access_token = response["AuthenticationResult"]["AccessToken"]
        refresh_token = response["AuthenticationResult"]["RefreshToken"]

        logger.info("Authentication successful")

        return id_token, access_token, refresh_token

    except ClientError as e:
        logger.error(f"Authentication failed: {e.response['Error']['Message']}")
        return None, None, None
    except BotoCoreError as e:
        logger.error(f"AWS SDK error: {str(e)}")
        return None, None, None
    except Exception as e:
        logger.error(f"Unexpected error during authentication: {e}")
        return None, None, None
    
def save_token(token):
    """Save token to a file"""
    logger.info(f"Saving token to {TOKEN_FILE}...")
    try:
        with open(TOKEN_FILE, "w") as f:
            f.write(token)
        logger.info("Token saved successfully.")
    except Exception as e:
        logger.error(f"Failed to save token: {e}")

def load_token():
    """Load token from a file"""
    logger.info(f"Attempting to load token from {TOKEN_FILE}...")
    try:
        if os.path.exists(TOKEN_FILE):
            logger.debug("Token file found.")
            with open(TOKEN_FILE, "r") as f:
                token = f.read().strip()
                if token:
                    logger.info("Token loaded successfully.")
                    return token
                else:
                    logger.warning("Token file is empty.")
                    return None
        else:
            logger.warning("Token file not found.")
            return None
    except Exception as e:
        logger.error(f"Failed to load token: {e}")
        return None