import json
import requests

class IsAirport:
    def __init__(self, base_url):
        self.base_url = base_url

    def is_Airport(self, lat, lon):
        params = {
            "lat": lat,
            "lon": lon
        }
        try:
            response = requests.get(
                self.base_url,
                params=params
            )

            if response.status_code == 200:
                return response.json()
            else:
                return {"status": response.status_code}
        except requests.RequestException as e:
            return f"Request failed: {str(e)}"


