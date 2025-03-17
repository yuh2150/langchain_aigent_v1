import requests
import json
import os
from base64 import b64encode
# from geoCoding import GeoCodingAPI
# import pytz
# from datetime import datetime, timedelta
def basic_auth(username, password):
    token = b64encode(f"{username}:{password}".encode('utf-8')).decode("ascii")
    return f'Basic {token}'
class QuotesAPI:
    def __init__(self, base_url):
        self.base_url = base_url
        self.headers = {
            'Content-Type': 'application/json',
            'Accept': 'application/json',
            'Authorization': basic_auth(os.getenv("JUPITER_USER"), os.getenv("JUPITER_PASS"))
        }
    def get_quotes(self, pickup_datetime, pickup_coords, destination_coords,fleetToken='yellow'):
        payload = json.dumps({
            "pickupDateTime": pickup_datetime,
            "pickup": {
                "latitude": float(pickup_coords['latitude']),
                "longitude": float(pickup_coords['longitude']),
            },
            "destination": {
                "latitude": float(destination_coords['latitude']),
                "longitude": float(destination_coords['longitude']),
            },
        })
        params = {
            "fleetToken": fleetToken,
            }
        try:
            response = requests.post(self.base_url, headers=self.headers, data=payload,params=params)
            if response.status_code == 200:
                return response.json()
            else:
                error_message = response.json().get("message", "Unknown error")
                return {"status": response.status_code,"error": error_message}
        except requests.RequestException as e:
            return {"error": str(e)}
# class Quote:
#     def __init__(self, quote_id, expires_at, vehicle_type, price_value, price_currency, luggage, passengers, provider_name, provider_phone):
#         self.quote_id = quote_id
#         self.expires_at = expires_at
#         self.vehicle_type = vehicle_type
#         self.price_value = price_value
#         self.price_currency = price_currency
#         self.luggage = luggage
#         self.passengers = passengers
#         self.provider_name = provider_name
#         self.provider_phone = provider_phone
#     def to_dict(self):
#         return {
#             "quote_id": self.quote_id,
#             "expires_at": self.expires_at,
#             "vehicle_type": self.vehicle_type,
#             "price_value": self.price_value,
#             "price_currency": self.price_currency,
#             "luggage": self.luggage,
#             "passengers": self.passengers,
#             "provider_name": self.provider_name,
#             "provider_phone": self.provider_phone
#         }
#     def __repr__(self):
#         return (f"Quote(quote_id={self.quote_id}, expires_at={self.expires_at}, vehicle_type={self.vehicle_type}, "
#                 f"price_value={self.price_value}, price_currency={self.price_currency}, luggage={self.luggage}, "
#                 f"passengers={self.passengers}, provider_name={self.provider_name}, provider_phone={self.provider_phone})")
if __name__ == "__main__":
    api = QuotesAPI(os.getenv("JUPITER_API") + "/demand/v1/quotes")
    pickup_datetime = '2025-03-10T09:53:44Z'
    pickup_coords = {'latitude': 10.7228245, 'longitude': 106.6606769}
    destination_coords = {'latitude': 16.0569804, 'longitude': 108.2025372}
    quotes_data = api.get_quotes(pickup_datetime, pickup_coords, destination_coords)
    print(quotes_data)
    quotes = []
