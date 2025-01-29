import boto3
import yaml
import os
from botocore.exceptions import BotoCoreError, ClientError
from app.logger import setup_logger

# Load configuration
with open("config/auth.yaml", "r") as file:
    config = yaml.safe_load(file)

TOKEN_FILE = "config/token.txt"

USER_POOL_ID = config["aws_cognito"]["user_pool_id"]
CLIENT_ID = config["aws_cognito"]["client_id"]
REGION = config["aws_cognito"]["region"]
AUTH_URL = config["aws_cognito"]["auth_url"]
USERNAME = config["credentials"]["username"]
PASSWORD = config["credentials"]["password"]

# Setup logging
logger = setup_logger()

def get_auth_token():
    """Authenticate with AWS Cognito and return the token"""
    try:
        # Create Cognito Identity Provider client
        client = boto3.client("cognito-idp", region_name=REGION)

        # Authenticate user
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
    
def save_token(token):
    """Save token to a file"""
    with open(TOKEN_FILE, "w") as f:
        f.write(token)

def load_token():
    """Load token from a file"""
    if os.path.exists(TOKEN_FILE):
        with open(TOKEN_FILE, "r") as f:
            return f.read().strip()
    return None    
