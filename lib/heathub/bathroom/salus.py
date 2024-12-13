import boto3
from botocore.auth import SigV4Auth
from botocore.awsrequest import AWSRequest
import aiohttp
import time
import datetime
from typing import Any, Dict, Optional
from urllib.parse import urlparse

# Import the utility classes and constants
from lib.heathub.utils import (
    ConfigManager,
    LogManager,
    Helper,
    DEVICE_SALUS_BUTTON_BATHROOM,
    LOG_TYPE_ERROR,
)

# Initialize managers
config_manager = ConfigManager()
log_manager = LogManager()

# Load configuration
config_salus = config_manager.get_config().get("salus", {})


class SmartButton:
    """Class representing the smart button device."""

    heat_status_off = "off"
    heat_status_on = "on"

    def __init__(self):
        self.user_pool_id = config_salus.get("account_user_pool_id")
        self.client_id = config_salus.get("account_client_id")
        self.identity_id = config_salus.get("account_identity_id")
        self.region = config_salus.get("account_region")
        self.username = config_salus.get("account_username")
        self.password = config_salus.get("account_password")
        self.endpoint = config_salus.get("account_iot_endpoint")
        self.thing_name = config_salus.get("account_device_button_bathroom_id")
        self.boiler_working_time = float(
            config_salus.get("device_button_bathroom_boiler_working_time", 0)
        )
        self.auth_client = boto3.client("cognito-idp", region_name=self.region)
        self.identity_client = boto3.client("cognito-identity", region_name=self.region)

    async def authenticate_user(self) -> str:
        # Authenticate the user and retrieve the ID token.

        auth_params = {
            "AuthFlow": "USER_PASSWORD_AUTH",
            "ClientId": self.client_id,
            "AuthParameters": {"USERNAME": self.username, "PASSWORD": self.password},
        }

        auth_response = self.auth_client.initiate_auth(**auth_params)
        id_token = auth_response["AuthenticationResult"]["IdToken"]
        return id_token

    async def get_aws_credentials(self, id_token: str) -> Dict[str, Any]:
        # Retrieve AWS credentials using the ID token.

        credentials_response = self.identity_client.get_credentials_for_identity(
            IdentityId=self.identity_id,
            Logins={
                f"cognito-idp.{self.region}.amazonaws.com/{self.user_pool_id}": id_token
            },
        )
        return credentials_response["Credentials"]

    async def make_signed_request(self, credentials: Dict[str, Any]) -> Any:
        # Make a signed GET request to the AWS IoT endpoint.

        request_url = f"{self.endpoint}/things/{self.thing_name}/shadow"
        aws_credentials = (
            boto3.Session(
                aws_access_key_id=credentials["AccessKeyId"],
                aws_secret_access_key=credentials["SecretKey"],
                aws_session_token=credentials["SessionToken"],
            )
            .get_credentials()
            .get_frozen_credentials()
        )

        request = AWSRequest(method="GET", url=request_url)
        SigV4Auth(aws_credentials, "iotdata", self.region).add_auth(request)

        # Extract host from endpoint URL
        parsed_url = urlparse(self.endpoint)
        host = parsed_url.netloc

        headers = {
            "X-Amz-Security-Token": credentials["SessionToken"],
            "X-Amz-Date": request.headers["X-Amz-Date"],
            "Authorization": request.headers["Authorization"],
            "Accept": "application/json",
            "Host": host,
        }

        async with aiohttp.ClientSession() as session:
            async with session.get(request_url, headers=headers) as response:
                response_json = None
                response_text = None
                if response.status == 200:
                    response_json = await response.json()
                else:
                    response_text = await response.text()
                return response.status, response_json, response_text

    async def get_heat_status(self) -> Optional[str]:
        # Retrieve the heat status based on the button presses.

        try:
            id_token = await self.authenticate_user()
            credentials = await self.get_aws_credentials(id_token)
            status, response_json, response_text = await self.make_signed_request(
                credentials
            )
            if status == 200 and response_json:
                try:
                    reported = response_json["state"]["reported"]["11"]["properties"]
                    metadata = response_json["metadata"]["reported"]["11"]["properties"]

                    button_up_pressed_timestamp = metadata[
                        "ep2:sButtonS:ButtonPressed"
                    ]["timestamp"]
                    button_down_pressed_timestamp = metadata[
                        "ep3:sButtonS:ButtonPressed"
                    ]["timestamp"]

                    # Convert timestamps to human-readable format
                    button_up_pressed_date = datetime.datetime.fromtimestamp(
                        button_up_pressed_timestamp
                    ).strftime("%Y-%m-%d %H:%M:%S")
                    button_down_pressed_date = datetime.datetime.fromtimestamp(
                        button_down_pressed_timestamp
                    ).strftime("%Y-%m-%d %H:%M:%S")

                    # Get the current time and hour
                    current_time = int(time.time())
                    current_hour = datetime.datetime.now().hour
                    current_minute = datetime.datetime.now().minute

                    # Check if the current time is between 11 PM and 5:30 AM
                    if (
                        (current_hour == 23)
                        or (0 <= current_hour < 5)
                        or (current_hour == 5 and current_minute < 30)
                    ):
                        log_manager.set_log(
                            "Button press ignored due to time restriction (11 PM - 5:30 AM)",
                            device=DEVICE_SALUS_BUTTON_BATHROOM,
                        )
                        return self.heat_status_off

                    heat_status = self.heat_status_off
                    if button_up_pressed_timestamp > button_down_pressed_timestamp:
                        time_difference = current_time - button_up_pressed_timestamp
                        time_difference_minutes = time_difference / 60
                        if 0 <= time_difference_minutes < self.boiler_working_time:
                            log_manager.set_log(
                                f"Button pressed up at {button_up_pressed_date}; "
                                f"Button pressed down at {button_down_pressed_date}; "
                                f"Waiting time: {self.boiler_working_time}; "
                                f"Time difference (minutes): {time_difference_minutes}",
                                device=DEVICE_SALUS_BUTTON_BATHROOM,
                            )
                            heat_status = self.heat_status_on
                    return heat_status
                except KeyError as e:
                    log_manager.set_log(
                        f"KeyError: {e}",
                        device=DEVICE_SALUS_BUTTON_BATHROOM,
                        log_type=LOG_TYPE_ERROR,
                    )
            else:
                log_manager.set_log(
                    f"Request failed with status {status}: {response_text}",
                    device=DEVICE_SALUS_BUTTON_BATHROOM,
                    log_type=LOG_TYPE_ERROR,
                )
        except Exception as e:
            log_manager.set_log(
                f"Exception in get_heat_status: {e}",
                device=DEVICE_SALUS_BUTTON_BATHROOM,
                log_type=LOG_TYPE_ERROR,
            )
        return None
