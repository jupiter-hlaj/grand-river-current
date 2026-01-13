import boto3
import json

DYNAMO_TABLE = "GRT_Bus_State"
dynamodb = boto3.resource('dynamodb')
table = dynamodb.Table(DYNAMO_TABLE)

STOP_ID = "1000"
ROUTE_ID = "1"
NEW_HEADSIGN = "The Boardwalk Station" # From live bus data

def update_stop_routes():
    print(f"Updating STOP_ROUTES#{STOP_ID} for Route {ROUTE_ID} to headsign '{NEW_HEADSIGN}'...")
    
    response = table.get_item(Key={'PK': f"STOP_ROUTES#{STOP_ID}"})
    item = response.get('Item', {})
    routes = item.get('Routes', [])

    found_and_updated = False
    new_routes_list = []
    for r in routes:
        if r.get('route_id') == ROUTE_ID:
            if r.get('headsign') != NEW_HEADSIGN:
                print(f"  Changing headsign from '{r.get('headsign')}' to '{NEW_HEADSIGN}'.")
                r['headsign'] = NEW_HEADSIGN
            new_routes_list.append(r)
            found_and_updated = True
        else:
            new_routes_list.append(r)
    
    if not found_and_updated:
        print(f"  Route {ROUTE_ID} not found in existing list. Adding with headsign '{NEW_HEADSIGN}'.")
        new_routes_list.append({'route_id': ROUTE_ID, 'headsign': NEW_HEADSIGN})

    table.put_item(Item={'PK': f"STOP_ROUTES#{STOP_ID}", 'Routes': new_routes_list})
    print(f"Successfully updated STOP_ROUTES#{STOP_ID}.")

if __name__ == '__main__':
    update_stop_routes()
