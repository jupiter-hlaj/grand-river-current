import boto3
import json
from decimal import Decimal

session = boto3.Session()
dynamodb = session.resource('dynamodb')
table = dynamodb.Table('GRT_Bus_State')

def find_nearby():
    # Get Stop 1000 location
    resp = table.get_item(Key={'PK': 'STOP#1000'})
    if 'Item' not in resp:
        print("Stop 1000 not found.")
        return

    target = resp['Item']
    lat = float(target['lat'])
    lon = float(target['lon'])
    print(f"Stop 1000: {target['name']} ({lat}, {lon})")

    # Scan all stops (inefficient but fine for this one-off)
    # In a real app we'd use GSI or Geospatial index
    scan = table.scan(FilterExpression='begins_with(PK, :s)', ExpressionAttributeValues={':s': 'STOP#'})
    
    print("\n--- Nearby Stops (< 150m) ---")
    for item in scan['Items']:
        if item['PK'] == 'STOP#1000' or item.get('type') != 'STATIC_STOP': continue
        
        slat = float(item['lat'])
        slon = float(item['lon'])
        
        # Simple Euclidean approx
        dist = ((slat - lat)**2 + (slon - lon)**2)**0.5
        if dist < 0.0015: # Approx 150m
            print(f"{item['PK']}: {item['name']} - Routes: ???")
            
            # Check routes for this stop
            stop_id = item['PK'].split('#')[1]
            r_resp = table.get_item(Key={'PK': f"STOP_ROUTES#{stop_id}"})
            if 'Item' in r_resp:
                routes = r_resp['Item'].get('Routes', [])
                r_str = ", ".join([f"{r['route_id']} {r['headsign']}" for r in routes])
                print(f"    Routes: {r_str}")

if __name__ == '__main__':
    find_nearby()
