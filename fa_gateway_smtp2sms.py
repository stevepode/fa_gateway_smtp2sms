# ---
# SMTP server receiving FortiAuthenticator emails and forwarding them as SMS.
# Functions as an SMS gateway for OTPs during guest Wi-Fi registration.
# ---
# Stefano Podestà - 03/11/2022
# Ver. 1.0
# MIT License
# ---

import asyncio
from aiosmtpd.controller import Controller
import requests
import json
import sys
import datetime
from email import message_from_bytes
from email.policy import default

# Base URL for the Aruba SMS REST API
BASE_URL = "https://smspanel.aruba.it/API/v1.0/REST/"

# Define message quality parameter for SMS (high quality)
MESSAGE_HIGH_QUALITY = "N"


def json_serial(obj):
    """
    Custom JSON serializer for datetime objects.
    
    Args:
        obj: Object to serialize.
        
    Returns:
        ISO formatted string if obj is datetime.
        
    Raises:
        TypeError: If obj type is not serializable.
    """
    if isinstance(obj, datetime.datetime):
        return obj.isoformat()
    raise TypeError("Type not serializable")


def login(username, password):
    """
    Authenticate with the SMS API and retrieve user/session keys.
    
    Args:
        username (str): SMS API username.
        password (str): SMS API password.
    
    Returns:
        tuple: (user_key, session_key) on success, None on failure.
    """
    response = requests.get(f"{BASE_URL}login?username={username}&password={password}")
    if response.status_code != 200:
        return None
    user_key, session_key = response.text.split(';')
    return user_key, session_key


def send_sms(auth_keys, sms_payload):
    """
    Send an SMS using the Aruba SMS API.
    
    Args:
        auth_keys (tuple): Tuple containing user_key and session_key.
        sms_payload (dict): Dictionary containing SMS message and metadata.
    
    Returns:
        dict: API response parsed as JSON on success, None on failure.
    """
    headers = {
        'user_key': auth_keys[0],
        'Session_key': auth_keys[1],
        'Content-type': 'application/json'
    }
    response = requests.post(
        f"{BASE_URL}sms",
        headers=headers,
        data=json.dumps(sms_payload, default=json_serial)
    )
    if response.status_code != 201:
        return None
    return json.loads(response.text)


class SMTPHandler:
    """
    Custom SMTP handler for receiving emails and converting them to SMS.
    """
    async def handle_DATA(self, server, session, envelope):
        """
        Handle incoming email DATA events from the SMTP server.
        
        Args:
            server: SMTP server instance.
            session: SMTP session information.
            envelope: SMTP envelope containing email content.
        
        Returns:
            str: SMTP response code after processing email.
        """
        peer = session.peer
        mail_from = envelope.mail_from
        rcpt_tos = envelope.rcpt_tos

        # Parse email message from raw bytes
        email_message = message_from_bytes(envelope.content, policy=default)

        # Extract recipient phone number from email address
        recipient_number = str(rcpt_tos[0]).split('@')[0]
        print(f"Recipient: {recipient_number}")
        print(f"Email content: {email_message}")

        # Extract message content from email body
        message_content = str(email_message).split('>')[2]

        # Authenticate with SMS API
        auth_keys = login("john", "paswd1234")
        if not auth_keys:
            print("Unable to login..")
            sys.exit(-1)

        # Prepare SMS payload
        sms_payload = {
            "message": message_content,
            "message_type": MESSAGE_HIGH_QUALITY,
            "returnCredits": False,
            "recipient": [recipient_number],
            "sender": "ACME",
        }

        # Send SMS via API
        sent_sms = send_sms(auth_keys, sms_payload)

        if sent_sms and sent_sms.get('result') == "OK":
            print("SMS sent successfully!")
        else:
            print("Error sending SMS.")

        return '250 OK'


async def main(loop):
    """
    Main coroutine to start the SMTP server.
    
    Args:
        loop: Asyncio event loop.
    """
    handler = SMTPHandler()
    # Bind the SMTP server to a specific host and port
    controller = Controller(handler, hostname='192.168.1.2', port=14725)
    controller.start()


if __name__ == "__main__":
    loop = asyncio.get_event_loop()
    loop.create_task(main(loop=loop))

    try:
        # Run the event loop indefinitely until interrupted
        loop.run_forever()
    except KeyboardInterrupt:
        pass
