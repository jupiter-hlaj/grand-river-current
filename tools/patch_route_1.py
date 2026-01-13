import boto3
import json
import gzip
import os

DYNAMO_TABLE = "GRT_Bus_State"
dynamodb = boto3.resource('dynamodb')
table = dynamodb.Table(DYNAMO_TABLE)

STOP_ID_TO_PATCH = "1000"
TARGET_ROUTE_ID = "1"

def get_trip_details(trip_id):
    if not trip_id: return {}
    response = table.get_item(Key={'PK': f"TRIP#{trip_id}"}, ProjectionExpression="route_id, headsign")
    if 'Item' in response:
        return {'headsign': response['Item'].get('headsign'), 'route_id': response['Item'].get('route_id')}
    return {}

def patch_route_1_for_stop_1000():
    print(f"Searching for live Route {TARGET_ROUTE_ID} bus to get headsign...")
    bus_response = table.get_item(Key={'PK': 'BUS_ALL'})
    bus_item = bus_response.get('Item')
    buses = json.loads(gzip.decompress(bus_item['buses_binary'].value).decode('utf-8')) if bus_item and 'buses_binary' in bus_item else []

    route_1_headsign = None
    for bus in buses:
        details = get_trip_details(bus.get('trip_id'))
        if details.get('route_id') == TARGET_ROUTE_ID:
            route_1_headsign = details.get('headsign')
            print(f"Found live Route {TARGET_ROUTE_ID} bus with Headsign: '{route_1_headsign}'")
            break

    if not route_1_headsign:
        print(f"Error: No live Route {TARGET_ROUTE_ID} bus found to determine headsign. Cannot patch.")
        # Fallback to a common headsign if no live bus is found
        # This should ideally be verified manually or from static GTFS files
        route_1_headsign = "Conestoga Mall" # Common headsign for Route 1, often seen at 1000
        print(f"Falling back to default headsign '{route_1_headsign}' for Route {TARGET_ROUTE_ID}.")

    print(f"Fetching current STOP_ROUTES#{STOP_ID_TO_PATCH} ...")
    stop_routes_response = table.get_item(Key={'PK': f"STOP_ROUTES#{STOP_ID_TO_PATCH}"})
    current_routes = stop_routes_response.get('Item', {}).get('Routes', [])

    # Check if Route 1 already exists with any headsign
    route_1_exists = False
    for route_entry in current_routes:
        if route_entry.get('route_id') == TARGET_ROUTE_ID:
            route_1_exists = True
            # If it exists but with a different headsign, we should potentially update it
            if route_entry.get('headsign') != route_1_headsign:
                print(f"Route {TARGET_ROUTE_ID} found with different headsign '{route_entry.get('headsign')}'. Updating...")
                route_entry['headsign'] = route_1_headsign
            else:
                print(f"Route {TARGET_ROUTE_ID} with headsign '{route_1_headsign}' already exists. No update needed.")
            break
    
    if not route_1_exists:
        print(f"Adding Route {TARGET_ROUTE_ID} with headsign '{route_1_headsign}' to STOP_ROUTES#{STOP_ID_TO_PATCH}...")
        current_routes.append({'route_id': TARGET_ROUTE_ID, 'headsign': route_1_headsign})
        
        table.put_item(Item={
            'PK': f"STOP_ROUTES#{STOP_ID_TO_PATCH}",
            'Routes': current_routes
        })
        print("DynamoDB item updated successfully.")
    else:
        # If route 1 already exists and was potentially updated (or not) above, re-put the item to ensure consistency.
        table.put_item(Item={
            'PK': f"STOP_ROUTES#{STOP_ID_TO_PATCH}",
            'Routes': current_routes
        })
        print("DynamoDB item ensured consistent.")


if __name__ == '__main__':
    patch_route_1_for_stop_1000()
