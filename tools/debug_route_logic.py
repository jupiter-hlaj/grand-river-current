import sys
import os
sys.path.append(os.path.join(os.getcwd(), '.gemini/tmp/lib'))
sys.path.append(os.path.join(os.getcwd(), 'grand_river_current/pkg_ingest'))

import boto3
import json
import gzip
from decimal import Decimal

# Configure AWS
session = boto3.Session()
dynamodb = session.resource('dynamodb')
table = dynamodb.Table('GRT_Bus_State') # Ensure this matches the actual table name

def decimal_default(obj):
    if isinstance(obj, Decimal):
        return int(obj)
    raise TypeError

def check_stop_1000():
    stop_id = '1000'
    print(f"--- Debugging Stop {stop_id} ---")

    # 1. Get Allowed Routes
    stop_routes_resp = table.get_item(Key={'PK': f"STOP_ROUTES#{stop_id}"})
    if 'Item' not in stop_routes_resp:
        print("Error: STOP_ROUTES not found.")
        return
    
    stop_routes_item = stop_routes_resp['Item']
    allowed_routes = { (r['route_id'], r['headsign']) for r in stop_routes_item.get('Routes', []) }
    print(f"Allowed Routes: {allowed_routes}")

    # 2. Get Live Buses
    bus_resp = table.get_item(Key={'PK': 'BUS_ALL'})
    if 'Item' not in bus_resp:
        print("Error: BUS_ALL not found.")
        return
    
    buses = json.loads(gzip.decompress(bus_resp['Item']['buses_binary'].value).decode('utf-8'))
    print(f"Total Live Buses: {len(buses)}")

    # 3. Check for Route 4 Buses
    route_4_buses = []
    
    # We need to resolve trip details to get route_ids
    unique_trip_ids = {bus['trip_id'] for bus in buses if bus.get('trip_id')}
    print(f"Unique Trip IDs: {len(unique_trip_ids)}")
    
    # Just check a few for debugging or all if feasible? 
    # Let's just resolve the ones that LOOK interesting (e.g. if we can guess from another field)
    # Actually, the ingest process puts route_id in BUS_ALL? No, the reader does the join.
    # The reader code:
    # unique_trip_ids = {bus['trip_id'] for bus in buses if bus.get('trip_id')}
    # all_trip_keys = [{'PK': f"TRIP#{trip_id}"} for trip_id in unique_trip_ids]
    # ... batch get ...
    
    # Let's manually get trip details for ANY bus that MIGHT be relevant.
    # Since we don't know which bus is Route 4 without the trip, we have to look at all of them 
    # OR we can scan the TRIP table for Route 4 trips and see if any buses match.
    
    # Let's try to match buses to allowed_routes by fetching their trip details.
    # This might be slow for all buses, so let's just fetch the first 50 to see if we find ANY Route 4.
    
    # Actually, I'll search the TRIP_STOP_TIMES for the stop_id to find RELEVANT trips first.
    # No, that's not how the reader works. Reader iterates ALL buses.
    
    print("Checking first 100 buses for Route 4 candidates...")
    
    found_route_4 = False
    
    # We can use batch_get_item
    keys = [{'PK': f"TRIP#{bus['trip_id']}"} for bus in buses if bus.get('trip_id')][:100]
    
    # Simplified batch get (just one batch for now)
    if keys:
        resp = dynamodb.batch_get_item(RequestItems={table.name: {'Keys': keys}})
        trips = resp.get('Responses', {}).get(table.name, [])
        
        trip_map = {t['PK'].split('#')[1]: t for t in trips}
        
        for bus in buses:
            tid = bus.get('trip_id')
            if tid in trip_map:
                trip = trip_map[tid]
                rid = trip.get('route_id')
                head = trip.get('headsign')
                
                if rid == '4':
                    print(f"Found Route 4 Bus! ID: {bus['id']}, Trip: {tid}, Headsign: {head}")
                    found_route_4 = True
                    
                    # Now check why it might be filtered
                    # 1. Allowed Route check
                    if (rid, head) not in allowed_routes:
                        print(f"  -> BLOCKED: Not in allowed routes. {(rid, head)}")
                        # Check if maybe headsign mismatch?
                        # allowed might have specific headsigns.
                    else:
                        print(f"  -> Allowed.")
                        
                    # 2. Schedule Check
                    # We need TRIP_STOP_TIMES#{tid}
                    tst_resp = table.get_item(Key={'PK': f"TRIP_STOP_TIMES#{tid}"})
                    if 'Item' in tst_resp:
                        stop_times = tst_resp['Item']['StopTimes']
                        # Find our stop
                        target = next((st for st in stop_times if str(st['stop_id']) == stop_id), None)
                        if target:
                            print(f"  -> Stop found in schedule. Seq: {target['stop_sequence']}, Bus Seq: {bus.get('current_stop_sequence')}")
                            if target['stop_sequence'] < bus.get('current_stop_sequence'):
                                print("  -> PASSED: Bus has passed the stop.")
                            else:
                                print("  -> VALID: Bus is approaching.")
                        else:
                            print("  -> BLOCKED: Stop not in trip schedule.")
                    else:
                        print("  -> BLOCKED: No schedule found for trip.")
                        
    if not found_route_4:
        print("No Route 4 buses found in the sample.")

if __name__ == '__main__':
    check_stop_1000()
