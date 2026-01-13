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
        print(f"Download failed: {r.status_code}")
        return {"status": "FAIL", "reason": r.text[:200]}

    z = zipfile.ZipFile(io.BytesIO(r.content))

    # Process stop_times.txt using a streaming approach
    print("Processing stop_times (streaming)...")
    
    current_trip_id = None
    current_stop_times = []
    trips_processed = 0
    
    with z.open('stop_times.txt') as f, table.batch_writer() as writer:
        # Sort by trip_id, stop_sequence if possible? No, we can't assume sort order in zip stream easily without reading all.
        # But usually GTFS stop_times are grouped by trip_id. Let's assume they are grouped.
        reader = csv.DictReader(io.TextIOWrapper(f, 'utf-8'))
        
        # We need to buffer by trip_id. Since file is usually sorted by trip_id, we can write when trip_id changes.
        # If not sorted, this simple streaming won't work perfectly (might overwrite/split items).
        # Standard GTFS is often grouped by trip.
        
        # Safe fallback: Use a smaller in-memory buffer, e.g. 500 trips, then write.
        trip_buffer = {} 
        
        for row in reader:
            trip_id = row.get('trip_id')
            arrival_time = row.get('arrival_time')
            stop_id = row.get('stop_id')
            stop_sequence = row.get('stop_sequence')
            
            if trip_id and arrival_time and stop_id and stop_sequence:
                if trip_id not in trip_buffer:
                    trip_buffer[trip_id] = []
                
                trip_buffer[trip_id].append({
                    'stop_id': stop_id,
                    'arrival_time': arrival_time,
                    'stop_sequence': int(stop_sequence)
                })
                
                # If buffer gets too big (e.g. 100 trips), write them out and clear
                if len(trip_buffer) >= 100:
                    for tid, stops in trip_buffer.items():
                        stops.sort(key=lambda x: x['stop_sequence'])
                        writer.put_item(Item={
                            'PK': f"TRIP_STOP_TIMES#{tid}",
                            'StopTimes': stops,
                            'type': 'TRIP_STOP_TIMES'
                        })
                        trips_processed += 1
                    print(f"Flushed {len(trip_buffer)} trips. Total: {trips_processed}")
                    trip_buffer = {} # Clear buffer
                    time.sleep(0.2) # Small sleep to be kind to DynamoDB

        # Write remaining trips
        if trip_buffer:
            for tid, stops in trip_buffer.items():
                stops.sort(key=lambda x: x['stop_sequence'])
                writer.put_item(Item={
                    'PK': f"TRIP_STOP_TIMES#{tid}",
                    'StopTimes': stops,
                    'type': 'TRIP_STOP_TIMES'
                })
                trips_processed += 1
            print(f"Flushed final {len(trip_buffer)} trips.")

    print(f"TRIP_STOP_TIMES items processed: {trips_processed}")

    return {"status": "SUCCESS", "trip_stop_times_processed": trips_processed}