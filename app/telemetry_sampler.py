import time
import requests
import json
from dataclasses import dataclass

BASE_ENDPOINT_URL = "http://192.168.2.2/mavlink2rest/mavlink/vehicles/1/components/1/messages/"

ATTITUDE_FIELDS = ("pitch","roll","yaw")
VFR_HUD_FIELDS = ("heading", "groundspeed")
FIELDS_OF_INTEREST = {
    "ATTITUDE" : ATTITUDE_FIELDS,
    "VFR_HUD" : VFR_HUD_FIELDS
}



@dataclass
class TelemetryReading:
    pitch: float
    roll: float
    yaw: float
    heading: float
    groundspeed: float
    timestamp: float

    @classmethod
    def from_endpoint(cls, telemReading, timestamp):
        return cls(timestamp=timestamp, **{f: telemReading[f] for f in ATTITUDE_FIELDS + VFR_HUD_FIELDS})


def read_telem(): #Pulls the values from GETs, puts into object?
    combined_reading = {} 
    for endpoint_name in FIELDS_OF_INTEREST.keys():
        response = requests.get(BASE_ENDPOINT_URL + endpoint_name)
        if response.status_code == 200:
            res_data = response.json()
            for field_name in FIELDS_OF_INTEREST[endpoint_name]:
                combined_reading[field_name] = res_data["message"][field_name]
        else:
            print(f"Failed with status code: {response.status_code}")
            return None
        timestamp = time.monotonic()#Grab timestamp.
        # Create a new object here.
    reading = TelemetryReading.from_endpoint(combined_reading,timestamp)
    return reading

if __name__ == "__main__":
    while True:
        print(read_telem())
        time.sleep(1)
