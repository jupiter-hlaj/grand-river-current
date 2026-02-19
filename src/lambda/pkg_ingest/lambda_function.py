import json, boto3, requests, time, os, gzip
from datetime import datetime, timedelta
from google.transit import gtfs_realtime_pb2
from boto3.dynamodb.types import Binary
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

URL = "https://webapps.regionofwaterloo.ca/api/grt-routes/api/VehiclePositions"
DYNAMO_TABLE = os.environ['DYNAMO_TABLE']
dynamodb = boto3.resource('dynamodb')
table = dynamodb.Table(DYNAMO_TABLE)

def fetch_and_save():
   try:
       s = requests.Session()
       s.mount('https://', LegacyAdapter())
       response = s.get(URL, timeout=10)
       if response.status_code != 200: return 0
       
       feed = gtfs_realtime_pb2.FeedMessage()
       feed.ParseFromString(response.content)
       
       timestamp = int(time.time())
       bus_list = []
       for entity in feed.entity:
           if entity.HasField('vehicle'):
               v = entity.vehicle
               bus_list.append({
                   "id": v.vehicle.id,
                   "lat": round(v.position.latitude, 5),
                   "lon": round(v.position.longitude, 5),
                   "bearing": v.position.bearing,
                   "trip_id": v.trip.trip_id,
                   "current_stop_sequence": v.current_stop_sequence,
                   "timestamp": timestamp
               })
       
       if not bus_list: return 0

       compressed_data = gzip.compress(json.dumps(bus_list).encode('utf-8'))
       
       # Calculate TTL for 12 months from now
       ttl_timestamp = timestamp + (365 * 24 * 60 * 60) # ~1 year

       with table.batch_writer() as batch:
           # 1. Update the live data record
           batch.put_item(Item={
               'PK': 'BUS_ALL',
               'updated_at': timestamp,
               'buses_binary': compressed_data,
               'count': len(bus_list)
           })
           # 2. Write the historical record with a TTL
           batch.put_item(Item={
               'PK': f'BUS_HISTORY#{timestamp}',
               'buses_binary': compressed_data,
               'count': len(bus_list),
               'ttl': ttl_timestamp
           })

       print(f"Updated live data and saved history for {len(bus_list)} buses.")
       return len(bus_list)
   except Exception as e:
       print(f"Error: {e}")
       return 0

def lambda_handler(event, context):
    # Triggered by EventBridge Scheduler at rate(1 minute).
    # Each invocation performs a single fetch; the scheduler handles the cadence.
    count = fetch_and_save()
    return {"status": "SUCCESS", "buses_updated": count}
