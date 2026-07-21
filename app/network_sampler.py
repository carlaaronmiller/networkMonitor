from dataclasses import dataclass
import psutil
import time

COUNTER_FIELDS = ("bytes_sent", "bytes_recv", "packets_sent", "packets_recv", "errin", "errout", "dropin", "dropout")
COUNTER_RATES = ("bps_sent","bps_recv","pps_sent","pps_recv","errin_ps", "errout_ps", "dropin_ps", "dropout_ps")
#INTERFACES = ("eth0","wlan0")
    
#Example reading.
# {'lo': snetio(bytes_sent=547971, bytes_recv=547971, packets_sent=5075, packets_recv=5075, errin=0, errout=0, dropin=0, dropout=0),

@dataclass
class InterfaceReading:
    bytes_sent: int
    bytes_recv: int
    packets_sent: int
    packets_recv: int
    errin: int
    errout: int
    dropin: int
    dropout: int
    timestamp: float

    @classmethod  # Use class method here because we're returning a class instance.
    def from_psutil(cls, reading, timestamp):
        # **notation is unpacking a dictionary, so in practice this is 
        #  giving all the counter field attributes.
        return cls(timestamp=timestamp, **{f: getattr(reading, f) for f in COUNTER_FIELDS})
        
class NetworkSampler:
    def __init__(self, interfaces=("eth0", "wlan0")):
        self.interfaces = interfaces #List of the interfaces, eth and wlan.
        self.last: dict[str, InterfaceReading] = {} #Dictionary containing:
        #interface_name: last reading
    
    # The psutils function gives the total amount of traffic sent.
    # So we can divide the total by period to get rate at that point.
    def sample(self) -> dict: 
        now = time.monotonic()#Grab timestamp:
        counters = psutil.net_io_counters(pernic=True)#Grab the Iface readings: 
        result = {}

        for iface in self.interfaces: #For both interfaces in the list.
            new = InterfaceReading.from_psutil(counters[iface], now)  # Instantiate a new reading object. Note: different naming for windows interfaces.
            old = self.last.get(iface)
            if old is not None:
                delta_t = new.timestamp - old.timestamp
                result[iface] = {
                    c_rate: (getattr(new, c_field) - getattr(old, c_field)) / delta_t
                    for c_field, c_rate in zip(COUNTER_FIELDS, COUNTER_RATES)
                }
            else:
                # No prior reading yet (first tick for this interface) - report zero rather
                # than omitting the key, so callers never have to special-case a missing interface.
                result[iface] = {c_rate: 0.0 for c_rate in COUNTER_RATES}

            self.last[iface] = new #Update last.
        #Do something with the result here, write it out or publish.
        return result
    
if __name__ == "__main__":
    nS = NetworkSampler()
    while True:
        reading = nS.sample()
        print(reading["eth0"])
        time.sleep(1)