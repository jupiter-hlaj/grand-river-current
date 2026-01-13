import json, boto3, requests, os, io, zipfile, csv, time, ssl
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

STATIC_URL = "https://webapps.regionofwaterloo.ca/api/grt-routes/api/staticfeeds/0"
DYNAMO_TABLE = os.environ['DYNAMO_TABLE']
dynamodb = boto3.resource('dynamodb')
table = dynamodb.Table(DYNAMO_TABLE)

def lambda_handler(event, context):
    print(f"Downloading Static GTFS from {STATIC_URL}...")
    s = requests.Session()
    s.mount('https://', LegacyAdapter())
    headers = { 'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36' }
    r = s.get(STATIC_URL, headers=headers)
    
    if r.status_code != 200:
        return {"status": "FAIL", "reason": r.text[:200]}

    z = zipfile.ZipFile(io.BytesIO(r.content))
    
    # Process stops.txt
    print("Processing stops...")
    stops_count = 0
    with z.open('stops.txt') as f, table.batch_writer() as writer:
        reader = csv.DictReader(io.TextIOWrapper(f, 'utf-8'))
        for row in reader:
            code = row.get('stop_code') or row.get('stop_id')
            if not code: continue
            writer.put_item(Item={
                'PK': f"STOP#{code}", 'lat': row.get('stop_lat'),
                'lon': row.get('stop_lon'), 'name': row.get('stop_name'),
                'type': 'STATIC_STOP'
            })
            stops_count += 1
            if stops_count % 500 == 0: time.sleep(0.1)

    # Process trips.txt to build a trip_id -> {route_id, headsign} map in memory
    print("Processing trips (for in-memory map)...")
    trip_to_route_map = {}
    trips_count = 0
    with z.open('trips.txt') as f, table.batch_writer() as writer:
        reader = csv.DictReader(io.TextIOWrapper(f, 'utf-8'))
        for row in reader:
            trip_id = row.get('trip_id')
            route_id = row.get('route_id')
            headsign = row.get('trip_headsign')
            if trip_id and route_id: 
                trip_to_route_map[trip_id] = {'route_id': route_id, 'headsign': headsign}
                writer.put_item(Item={
                    'PK': f"TRIP#{trip_id}",
                    'headsign': headsign,
                    'route_id': route_id,
                    'type': 'STATIC_TRIP'
                })
                trips_count += 1
                if trips_count % 500 == 0: time.sleep(0.1)

    # Process stop_times.txt to build stop_id -> set of (route_id, headsign) tuples
    print("Processing stop_times and building STOP_ROUTES mapping...")
    stop_routes_map = {}
    with z.open('stop_times.txt') as f:
        reader = csv.DictReader(io.TextIOWrapper(f, 'utf-8'))
        for row in reader:
            stop_id = row.get('stop_id')
            trip_id = row.get('trip_id')
            
            if stop_id and trip_id and trip_id in trip_to_route_map:
                route_info = trip_to_route_map[trip_id]
                route_id = route_info['route_id']
                headsign = route_info['headsign']
                if stop_id not in stop_routes_map:
                    stop_routes_map[stop_id] = set()
                stop_routes_map[stop_id].add((route_id, headsign))

    # Write STOP_ROUTES#<stop_id> items to DynamoDB
    stop_routes_count = 0
    with table.batch_writer() as writer:
        for stop_id, route_info_set in stop_routes_map.items():
            route_list = [{'route_id': r[0], 'headsign': r[1]} for r in route_info_set]
            writer.put_item(Item={
                'PK': f"STOP_ROUTES#{stop_id}",
                'Routes': route_list,
                'type': 'STOP_ROUTE_MAP'
            })
            stop_routes_count += 1
            if stop_routes_count % 500 == 0: time.sleep(0.1)

    return {"status": "SUCCESS", "stops_processed": stops_count, "trips_processed": trips_count, "stop_routes_processed": stop_routes_count}