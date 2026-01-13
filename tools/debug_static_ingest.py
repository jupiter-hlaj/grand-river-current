import io
import zipfile
import csv
import sys
import os

sys.path.append(os.path.join(os.getcwd(), 'grand_river_current/pkg_ingest'))
import requests

STATIC_URL = "https://webapps.regionofwaterloo.ca/api/grt-routes/api/staticfeeds/0"

# Minimal Adapter for SSL issues
from requests.adapters import HTTPAdapter
from urllib3.poolmanager import PoolManager
from urllib3.util.ssl_ import create_urllib3_context

class LegacyAdapter(HTTPAdapter):
    def init_poolmanager(self, connections, maxsize, block=False):
        ctx = create_urllib3_context()
        ctx.set_ciphers('DEFAULT@SECLEVEL=1')
        self.poolmanager = PoolManager(
            num_pools=connections, maxsize=maxsize, block=block, ssl_context=ctx
        )

def debug_ingest():
    print(f"Downloading Static GTFS from {STATIC_URL}...")
    s = requests.Session()
    s.mount('https://', LegacyAdapter())
    headers = { 'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36' }
    r = s.get(STATIC_URL, headers=headers)
    
    if r.status_code != 200:
        print(f"Download failed: {r.status_code}")
        return

    z = zipfile.ZipFile(io.BytesIO(r.content))
    
    # 1. Check Trips for Route 4
    print("Scanning trips.txt for Route 4...")
    trip_map = {} # trip_id -> headsign
    route_4_trips = 0
    
    with z.open('trips.txt') as f:
        reader = csv.DictReader(io.TextIOWrapper(f, 'utf-8'))
        for row in reader:
            if row['route_id'] == '4':
                trip_map[row['trip_id']] = row['trip_headsign']
                route_4_trips += 1
                
    print(f"Found {route_4_trips} trips for Route 4.")
    
    # 2. Check Stop Times for Stop 1000
    print("Scanning stop_times.txt for Stop 1000...")
    stop_1000_visits = 0
    stop_1000_routes = set()
    
    with z.open('stop_times.txt') as f:
        reader = csv.DictReader(io.TextIOWrapper(f, 'utf-8'))
        for row in reader:
            if row['stop_id'] == '1000':
                stop_1000_visits += 1
                tid = row['trip_id']
                if tid in trip_map:
                    headsign = trip_map[tid]
                    stop_1000_routes.add(headsign)

    print(f"Stop 1000 has {stop_1000_visits} total visits.")
    print(f"Routes serving Stop 1000 (Route 4 only): {stop_1000_routes}")

if __name__ == '__main__':
    debug_ingest()
