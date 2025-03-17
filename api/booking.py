import requests
import json
import os
from base64 import b64encode
def basic_auth(username, password):
    token = b64encode(f"{username}:{password}".encode('utf-8')).decode("ascii")
    return f'Basic {token}'
class BookingAPI:
    def __init__(self, base_url):
        self.base_url = base_url
        self.headers = {
            'Content-Type': 'application/json',
            'Accept': 'application/json',
            'Authorization': basic_auth(os.getenv("JUPITER_USER"), os.getenv("JUPITER_PASS"))
        }

    def create_booking(self, quote_id, passenger_info,fleetToken='yellow'):
        payload = {
            "quoteId": quote_id,
            "passenger": passenger_info
        }
        params = {
            "fleetToken": fleetToken,
            }
        try:
            response = requests.post(self.base_url, headers=self.headers, data=json.dumps(payload),params=params)
            if response.status_code == 200:
                return response.json()  # Successful response
            else:
                return {
                    "error": response.status_code,
                    "status": response.text
                }
        except requests.exceptions.RequestException as e:
            return {"error": "Request failed", "message": str(e)}