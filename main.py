from langchain_openai import ChatOpenAI

model = ChatOpenAI(model="gpt-4o", temperature=0)


# For this tutorial we will use custom tool that returns pre-defined values for weather in two cities (NYC & SF)

from typing import Literal, OrderedDict,     Union

from langchain_core.tools import tool
from typing_extensions import TypedDict
from typing import Annotated, Literal , List , Optional , Any
from pydantic import BaseModel, Field , field_validator, ValidationInfo , model_validator
from langgraph.graph.message import AnyMessage , add_messages
from langgraph.graph import StateGraph, MessagesState, START, END
import sys
import os
from flask import Flask, request, jsonify
import requests
from datetime import datetime
from api.booking import BookingAPI
from api.geoCoding import GeoCodingAPI
from api.getKey import OAuthClient
from api.getQuotes import QuotesAPI
from api.is_Airport import IsAirport
from langgraph.checkpoint.memory import MemorySaver
from langgraph.managed import IsLastStep, RemainingSteps
from chat_agent_executor import create_react_agent
from langchain_core.messages import AIMessage, HumanMessage, ToolMessage , SystemMessage, RemoveMessage
from langchain_core.runnables import Runnable
import uuid
memory = MemorySaver()

jupiterAPI = os.getenv('JUPITER_API')
quoteAPI = str(jupiterAPI) + "/demand/v1/quotes"
bookingsAPI  = str(jupiterAPI) + '/demand/v1/bookings'
app = Flask(__name__)
def getData_for_duckling(text, dims):
    url = 'http://rasa_duckling:8000/parse'
    data = {
        'locale': 'en_US',
        'text': text,
        'dims': dims,
        'tz': "Asia/Ho_Chi_Minh"
    }
    response = requests.post(url, data=data)
    if response.status_code == 200:
        json_response = response.json()
        # value = json_response[0]['value']['value']
        return json_response
    else:
        return f"Error: {response.status_code}"
class Quote:
    def __init__(self, quote_id, expires_at, vehicle_type, price_value, price_currency, luggage, passengers, provider_name, provider_phone):
        self.quote_id = quote_id
        self.expires_at = expires_at
        self.vehicle_type = vehicle_type
        self.price_value = price_value
        self.price_currency = price_currency
        self.luggage = luggage
        self.passengers = passengers
        self.provider_name = provider_name
        self.provider_phone = provider_phone
    def to_dict(self):
        return {
            "quote_id": self.quote_id,
            "expires_at": self.expires_at,
            "vehicle_type": self.vehicle_type,
            "price_value": self.price_value,
            "price_currency": self.price_currency,
            "luggage": self.luggage,
            "passengers": self.passengers,
            "provider_name": self.provider_name,
            "provider_phone": self.provider_phone
        }
    def __repr__(self):
        return (f"Quote(quote_id={self.quote_id}, expires_at={self.expires_at}, vehicle_type={self.vehicle_type}, "
                f"price_value={self.price_value}, price_currency={self.price_currency}, luggage={self.luggage}, "
                f"passengers={self.passengers}, provider_name={self.provider_name}, provider_phone={self.provider_phone})")
pick_up_result = None
destination_result = None
booking_details = None
class BookingCarDetails(BaseModel):
    """Details for the bookings car details"""
    name: str = Field(
        ...,
        description="The name of the person booking the ride.Do not autofill if not provided",
    )
    number_phone: str = Field(
        ...,
        description="The phone number of the user.Do not autofill if not provided",
    )
    pick_up_location: str = Field(
        ...,
        description="The location where the user will be picked up.Do not autofill if not provided",
    )
    destination_location: str = Field(
        ...,
        description="The destination location for the ride.Do not autofill if not provided"
    )
    pick_up_time: str = Field(
        ...,
        description="The time the user intends to be picked up. No format keeps the text related to time.Do not autofill if not provided"
    )
    flight_code: str = Field(
        ...,
        description="The flight code of the user.Do not autofill if not provided"
    )

    @field_validator('pick_up_location')
    @classmethod
    def validate_pickup(cls, value:str, info: ValidationInfo):
        global pick_up_result , destination_result ,booking_details
        geoCodingAPI = GeoCodingAPI()
        if value == '':
            return ''
        else :
            geoCoding_pickup = geoCodingAPI.get_geocoding(value)
            if geoCoding_pickup["status"] == "OK" :
                pick_up_result = geoCoding_pickup
                return geoCoding_pickup['results'][0]['formatted_address']
            else:
                raise ValueError(f"Invalid pick-up location: {value}")
    @field_validator('destination_location')
    @classmethod
    def validate_destination(cls, value : str, info: ValidationInfo):
        geoCodingAPI = GeoCodingAPI()
        global pick_up_result , destination_result ,booking_details
        if value == '':
            return ''
        else :
            geoCoding_destination = geoCodingAPI.get_geocoding(value)
            if geoCoding_destination["status"] == "OK":
                destination_result = geoCoding_destination
                return geoCoding_destination['results'][0]['formatted_address']
            else:
            
                raise ValueError(f"Invalid destination location: {value}")
    @field_validator('pick_up_time')
    @classmethod
    def validate_pick_up_time(cls, value : str):
        dimensions = ["time"]
        if value == '':
            return ''
        
        try:
            expected_format = "%Y-%m-%dT%H:%M:%S.%f%z"
            parsed_datetime = datetime.strptime(value, expected_format)
            return value
        except :
            data = getData_for_duckling(value,dimensions)
            if data and isinstance(data, list) and 'value' in data[0] and 'value' in data[0]['value']:
                return data[0]['value']['value']
            else:
                raise ValueError("Invalid time format")
StructuredResponse = Union[dict, BaseModel]
StructuredResponseSchema = Union[dict, type[BaseModel]]
class State(TypedDict):
    messages: Annotated[list[AnyMessage], add_messages]
    is_last_step: IsLastStep
    remaining_steps: RemainingSteps
    quote_id: str
    booking_info: BookingCarDetails 
    structured_response: StructuredResponse

@tool 
def check_Airport(pick_up_location: str) :
    """Call the function to check if pick_up_location is an airport"""
    API_Airport = IsAirport(base_url=jupiterAPI + '/v2/distance/airport')
    geoCodingAPI = GeoCodingAPI()
    geoCoding_pickup = geoCodingAPI.get_geocoding(pick_up_location)
    if geoCoding_pickup["status"] == "OK":
        pick_up_lat = geoCoding_pickup['results'][0]['geometry']['location']['lat']
        pick_up_lng = geoCoding_pickup['results'][0]['geometry']['location']['lng']  
        is_Airport = API_Airport.is_Airport(pick_up_lat, pick_up_lng)
    else: 
        is_Airport = [False]
    return is_Airport[0]
@tool 
def format_data(booking_details : BookingCarDetails):
    """Call function to format booking details."""
    geoCodingAPI = GeoCodingAPI()
    # geoCoding_destination =
    geoCoding_pickup =  geoCodingAPI.get_geocoding(booking_details.pick_up_location)
    geoCoding_destination = geoCodingAPI.get_geocoding(booking_details.destination_location)
    dimensions = ["time"]
    data = getData_for_duckling(booking_details.pick_up_time,dimensions)
    if data and isinstance(data, list) and 'value' in data[0] and 'value' in data[0]['value']:
        pick_up_time = data[0]['value']['value']
    return "booking details: \n" + f"Name: {booking_details.name}\n" + f"Phone number: {booking_details.number_phone}\n" + f"Pick up location: {geoCoding_pickup['results'][0]['formatted_address']}\n" + f"Destination location: {geoCoding_destination['results'][0]['formatted_address']}\n" + f"Pick up time: {pick_up_time}"
    
@tool(response_format="content_and_artifact")
def get_quotes(booking_details : BookingCarDetails):
    """Call function to fetches quotes for car bookings based on the provided booking details."""
    quotesAPI = QuotesAPI(os.getenv("JUPITER_API") + "/demand/v1/quotes")
    geoCodingAPI = GeoCodingAPI()
    # geoCoding_destination =
    geoCoding_pickup =  geoCodingAPI.get_geocoding(booking_details.pick_up_location)
    geoCoding_destination = geoCodingAPI.get_geocoding(booking_details.destination_location)
    # input_datetime = datetime.fromisoformat(pick_up_time)
    data = getData_for_duckling(booking_details.pick_up_time,["time"])
    if data and isinstance(data, list) and 'value' in data[0] and 'value' in data[0]['value']:
        pickup_datetime = data[0]['value']['value']
    # pickup_datetime = "2025-03-10T09:24:10.000Z"
    
    pickup_coords = { "latitude": float(geoCoding_pickup['results'][0]['geometry']['location']['lat']),"longitude": float(geoCoding_pickup['results'][0]['geometry']['location']['lng']),}
    destination_coords = { "latitude": float(geoCoding_destination['results'][0]['geometry']['location']['lat']),"longitude": float(geoCoding_destination['results'][0]['geometry']['location']['lng']),}
    quotes_data = quotesAPI.get_quotes(pickup_datetime, pickup_coords, destination_coords)
    quotes = []
    if quotes_data[0].get('status') and quotes_data[0].get('status') != 200:
        return {"context": quotes_data.get('error')}, {"quotes": None}
    for item in quotes_data:
        quote = Quote(
        quote_id=item['quoteId'],
        expires_at=item['expiresAt'],
        vehicle_type=item['vehicleType'],
        price_value=item['price']['value'],
        price_currency=item['price']['currency'] if 'currency' in item['price'] and item['price']['currency'] is not None else 'CAD',
        luggage=item['luggage'],
        passengers=item['passengers'],
        provider_name=item['provider']['name'],
        provider_phone=item['provider']['phone']
        )
        quotes.append(quote)
    response = []
    for quote in quotes:
        response.append({
            "title": f"{quote.vehicle_type} - {quote.price_value} {quote.price_currency}",
            "payload": f"{quote.quote_id}"
        })
    return {"context": "Please user chooses quote"}, {"quotes": response}
@tool
def accept_booking(quote_Id: str ,booking_details : BookingCarDetails ):
    """Call function to accept booking with quote_ID."""
    bookingAPI = BookingAPI(bookingsAPI)
    # quote_id = tracker.get_slot("quoteId")
    person_name = booking_details.name
    number_contact = booking_details.number_phone
    
    passenger_info = {
        "title": "Mr",
        "phone": number_contact,
        "firstName": person_name,
        "lastName": ""
    }
    response = bookingAPI.create_booking(
        quote_id=quote_Id,
        passenger_info=passenger_info
    )
    if response["status"] == "accepted" : 
        return "Booking accepted successfully"
    else:
        return response["status"]

# Truyền callable vào prompt
# chat_model = SomeLangChainModel(prompt=dynamic_prompt)
system_prompt = """
    You are a very powerful assistant. 
    If user express the intention to book a ride please guide the user through a booking process. 
    Start get booking details : name, number phone, pick up location, destination location, pick up time
    Ask one question at a time, even if you don't get all the info. Don't list the questions or greet the user. 
    Explain you're gathering info to help.
    Call "check_Airport" to check pick up location. If it is an airport, ask the user if they want to provide a flight code to facilitate the trip.
    Please call "format_data" before asking user confirm booking details.
    Please ask user confirm booking details
    Call "get_quotes" to get quotes for the booking details
    Call "accept_booking" to accept booking with quote_ID
    Returns the booking details
"""
from langchain_core.runnables import (
    Runnable,
    RunnableBinding,
    RunnableConfig,
)
from langgraph.prebuilt import InjectedStore
from langgraph.store.base import BaseStore

def save_memory(memory: str, *, config: RunnableConfig, store: Annotated[BaseStore, InjectedStore()]) -> str:
    '''Save the given memory for the current user.'''
    # This is a **tool** the model can use to save memories to storage
    user_id = config.get("configurable", {}).get("user_id")
    namespace = ("memories", user_id)
    store.put(namespace, f"memory_{len(store.search(namespace))}", {"data": memory})
    return f"Saved memory: {memory}"
from langgraph.store.memory import InMemoryStore
store = InMemoryStore()
tools = [get_quotes,format_data,check_Airport,accept_booking]
graph = create_react_agent(
    model,
    tools=tools,
    state_schema=State,
    response_format=BookingCarDetails,
    prompt=system_prompt,
    checkpointer=memory,
)
# while True:
#     user_input = input("You: ")
#     # print(state["booking_info"])
#     inputs["messages"].append(("user", user_input))
#     for s in graph.stream(inputs,config=config, stream_mode="values"):
#         message = s["messages"][-1]
#         if isinstance(message, tuple):
#             print(f"Assistant: {message[1]}")
#         else:
#             print(message.artifact if hasattr(message, "artifact") else None)
#             message.pretty_print()

class UserState:
    def __init__(self, user_id):
        self.user_id = user_id
        self.pickup_result = None
        self.destination_result = None
        self.booking_details = BookingCarDetails(
            name="",
            number_phone="",
            pick_up_location="",
            destination_location="",
            pick_up_time="",
            flight_code=""
        )

# Dùng dictionary thay vì list
user_states = {}

def get_user_state(user_id):
    if user_id not in user_states:
        user_states[user_id] = UserState(user_id)
    return user_states[user_id]

def process_chat(user_input, user_id):
    user_state = get_user_state(user_id)
    inputs = {"messages": []}  
    config = {"configurable": {"user":user_id,"thread_id": user_id}}
    inputs["messages"].append(("user", user_input))

    responses = []
    quotes = []

    for output in graph.stream(inputs, config=config, stream_mode="updates"):
        if isinstance(output, dict) and 'tools' in output:
            message = output['tools']['messages'][0]
            if hasattr(message, 'artifact') and message.artifact:
                quotes.append(message.artifact["quotes"])
        if isinstance(output, dict) and 'agent' in output:
            message = output['agent']['messages'][0]
            if isinstance(message, AIMessage) and message.content:
                responses.append(message.content)
            elif isinstance(message, dict):
                responses.append(message.get('content', ''))
        if isinstance(output, dict) and 'generate_structured_response' in output:
            user_state.booking_details = output['generate_structured_response']['structured_response'] 
    print("333" )    
    branch_state = graph.get_state(config, subgraphs=True)
    print(branch_state)
    formatted_responses = [
        {
            "recipient_id": user_id,
            **({"buttons": quotes[-1]} if quotes else {}),  # Chỉ thêm "quotes" nếu có dữ liệu
            "text": responses
        }
    ]

    return formatted_responses
@app.route("/chat", methods=["POST"])
def chat():
    data = request.get_json()
    user_id = data.get("sender", "")
    user_input = data.get("message", "")

    if not user_input:
        return jsonify({"error": "Message is required"}), 400

    responses = process_chat(user_input, user_id)
    user_state = get_user_state(user_id)
    
    response_data = OrderedDict([
        ("context", responses),
        ("booking_details", user_state.booking_details.model_dump()),  # Lấy từ user_state
        ("pickup_result", user_state.booking_details.pick_up_location),
        ("destination_result", user_state.booking_details.destination_location)
    ])

    return jsonify(response_data)



if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=5555)