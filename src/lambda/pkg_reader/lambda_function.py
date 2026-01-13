import json, boto3, os, gzip, time
from datetime import datetime, timedelta
from decimal import Decimal

DYNAMO_TABLE = os.environ['DYNAMO_TABLE']
dynamodb = boto3.resource('dynamodb')
table = dynamodb.Table(DYNAMO_TABLE)

# --- Helper Functions ---

def decimal_default(obj):
    if isinstance(obj, Decimal): return int(obj)
    raise TypeError

def response_proxy(code, body):
   return {
       "statusCode": code,
       "headers": {"Content-Type": "application/json", "Cache-Control": "no-cache"},
       "body": json.dumps(body, default=decimal_default)
   }

def batch_get_trip_details(keys):
    trip_details = {}
    if not keys: return trip_details
    unique_keys = list({(k['PK']): k for k in keys}.values()) # Deduplicate keys
    
    for i in range(0, len(unique_keys), 100):
        chunk = unique_keys[i:i + 100]
        request_items = {DYNAMO_TABLE: {'Keys': chunk, 'ProjectionExpression': 'PK, headsign, route_id'}}
        try:
            response = dynamodb.batch_get_item(RequestItems=request_items)
            for item in response.get('Responses', {}).get(DYNAMO_TABLE, []):
                trip_id = item['PK'].split('#')[1]
                trip_details[trip_id] = {'headsign': item.get('headsign'), 'route_id': item.get('route_id')}
        except Exception as e:
            print(f"[ERROR] Batch get failed: {e}")
            
    return trip_details

def get_schedule_for_bus(trip_id, target_stop_id, current_sequence):
    if not trip_id: return None, None, None
    response = table.get_item(Key={'PK': f"TRIP_STOP_TIMES#{trip_id}"})
    item = response.get('Item')
    if not item or 'StopTimes' not in item: return None, None, None
    stop_times = item['StopTimes']
    
    target_arrival, target_seq, next_stop_name = None, None, None
    current_seq_val = int(current_sequence) if current_sequence else 0
    
    for entry in stop_times:
        if str(entry['stop_id']) == str(target_stop_id) and current_seq_val <= (entry['stop_sequence'] + 1):
            target_arrival, target_seq = entry['arrival_time'], entry['stop_sequence']
            break 

    for entry in stop_times:
        if entry['stop_sequence'] > current_seq_val:
            stop_resp = table.get_item(Key={'PK': f"STOP#{entry['stop_id']}"})
            if 'Item' in stop_resp: next_stop_name = stop_resp['Item'].get('name')
            break
    return target_arrival, target_seq, next_stop_name

# --- Main Handler ---

def lambda_handler(event, context):
    try:
        params = event.get('queryStringParameters') or {}
        stop_id = params.get('stop_id')
        if not stop_id: return response_proxy(400, {"error": "Missing stop_id"})
        print(f"--- REQUEST START: stop_id={stop_id} ---")

        est_now = datetime.utcnow() - timedelta(hours=5)
        current_time_str = est_now.strftime('%H:%M:%S')

        # 1. Batch Fetch Core Data
        core_data_keys = [
            {'PK': f"STOP#{stop_id}"}, {'PK': f"STOP_ROUTES#{stop_id}"},
            {'PK': f"STOP_SCHEDULE#{stop_id}"}, {'PK': 'BUS_ALL'}
        ]
        response = dynamodb.batch_get_item(RequestItems={DYNAMO_TABLE: {'Keys': core_data_keys}})
        item_map = {item['PK']: item for item in response.get('Responses', {}).get(DYNAMO_TABLE, [])}
        
        stop_data = item_map.get(f"STOP#{stop_id}")
        if not stop_data: return response_proxy(404, {"error": "Stop not found"})
        
        allowed_routes = {(r['route_id'], r['headsign']) for r in item_map.get(f"STOP_ROUTES#{stop_id}", {}).get('Routes', [])}
        print(f"Allowed routes for Stop {stop_id}: {allowed_routes}")
        
        full_schedule = item_map.get(f"STOP_SCHEDULE#{stop_id}", {}).get('Schedule', [])
        bus_item = item_map.get('BUS_ALL')
        buses = json.loads(gzip.decompress(bus_item['buses_binary'].value).decode('utf-8')) if bus_item and 'buses_binary' in bus_item else []
        print(f"Found {len(buses)} total live buses in BUS_ALL.")

        # 2. Batch Enrich All Live Buses
        if buses:
            trip_keys = [{'PK': f"TRIP#{b.get('trip_id')}"} for b in buses if b.get('trip_id')]
            trip_details_map = batch_get_trip_details(trip_keys)
            for bus in buses:
                bus.update(trip_details_map.get(bus.get('trip_id'), {}))
                
        # 3. Filter Buses: Direct Matches vs. Ignored (for Hybrid check)
        final_buses, ignored_buses, live_route_keys = [], [], set()
        for bus in buses:
            bus_route_key = (bus.get('route_id'), bus.get('headsign'))
            if bus_route_key in allowed_routes:
                sched_time, target_seq, next_stop_name = get_schedule_for_bus(bus.get('trip_id'), stop_id, bus.get('current_stop_sequence'))
                if target_seq is not None:
                    bus.update({'next_scheduled_arrival': sched_time or "N/A", 'next_stop_name': next_stop_name, 'target_stop_sequence': target_seq})
                    final_buses.append(bus)
                    live_route_keys.add(bus_route_key)
                else: ignored_buses.append(bus)
            else: ignored_buses.append(bus)
        
        print(f"Final buses (direct matches after filter): {len(final_buses)}")
        print(f"Ignored buses (for hybrid check): {len(ignored_buses)}")
        if ignored_buses:
            print(f"First few ignored buses:")
            for i, b in enumerate(ignored_buses[:5]):
                print(f"  - ID: {b.get('id')}, Route: {b.get('route_id')}, Headsign: {b.get('headsign')}")

        # 4. Universal Hybrid Logic & Offline Schedules
        offline_schedules = []
        stop_lat = float(stop_data.get('lat', 0))
        stop_lon = float(stop_data.get('lon', 0))

        for r_id, r_headsign in allowed_routes:
            if (r_id, r_headsign) not in live_route_keys:
                next_departure = next((e for e in full_schedule if e['r'] == r_id and e['h'] == r_headsign and e['t'] > current_time_str), None) \
                                 or next((e for e in full_schedule if e['r'] == r_id and e['h'] == r_headsign), None)
                
                if next_departure:
                    next_departure_time = next_departure['t']
                    found_incoming = False
                    # Hybrid match: same route_id AND is physically close
                    # Removed restrictive headsign match for universal application
                    for bus in ignored_buses:
                        if bus.get('route_id') == r_id: 
                            try:
                                # Check proximity (simple Euclidean distance for quick check)
                                bus_lat = float(bus.get('lat', 0))
                                bus_lon = float(bus.get('lon', 0))
                                distance = ((bus_lat - stop_lat)**2 + (bus_lon - stop_lon)**2)**0.5
                                # Assuming 0.005 degrees is approx 500m (adjust as needed for GRT area)
                                if distance < 0.005: 
                                    print(f"    HYBRID MATCH FOUND (proximity): Bus {bus.get('id')} (Route {bus.get('route_id')} {bus.get('headsign')}) for target ({r_id}, {r_headsign})") 
                                    hybrid_bus = bus.copy()
                                    hybrid_bus.update({'headsign': r_headsign, 'next_scheduled_arrival': next_departure_time, 'target_stop_sequence': 0})
                                    _, _, next_stop_name = get_schedule_for_bus(hybrid_bus.get('trip_id'), None, hybrid_bus.get('current_stop_sequence'))
                                    hybrid_bus['next_stop_name'] = next_stop_name
                                    final_buses.append(hybrid_bus)
                                    live_route_keys.add((r_id, r_headsign)) 
                                    found_incoming = True
                                    break
                            except Exception as dist_err:
                                print(f"    Error calculating distance for hybrid check: {dist_err}")
                    
                    if not found_incoming:
                        print(f"    No hybrid match for ({r_id}, {r_headsign}). Adding to offline schedules.")
                        time_str = next_departure_time
                        h, m, s = map(int, time_str.split(':'))
                        if h >= 24: time_str = f"{h-24:02d}:{m:02d}:{s:02d}"
                        offline_schedules.append({"route_id": r_id, "headsign": r_headsign, "next_scheduled_arrival": time_str})

        print(f"--- REQUEST END: Returning {len(final_buses)} live buses, {len(offline_schedules)} offline schedules ---")
        return response_proxy(200, {
            "stop_details": {"id": stop_id, "lat": stop_data.get('lat'), "lon": stop_data.get('lon'), "name": stop_data.get('name')},
            "nearby_buses": final_buses,
            "offline_schedules": offline_schedules,
            "all_routes": [list(r) for r in allowed_routes]
        })
    except Exception as e:
        print(f"[ERROR] Lambda execution failed: {e}")
        import traceback
        traceback.print_exc()
        return response_proxy(500, {"error": "Internal server error."})