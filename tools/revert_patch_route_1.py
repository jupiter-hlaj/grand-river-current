import boto3
import json

DYNAMO_TABLE = "GRT_Bus_State"
dynamodb = boto3.resource('dynamodb')
table = dynamodb.Table(DYNAMO_TABLE)

STOP_ID = "1000"
ROUTE_ID = "1"
ORIGINAL_HEADSIGN = "Fairway Station" # The headsign before my last patch

def revert_stop_routes_patch():
    print(f"Reverting STOP_ROUTES#{STOP_ID} for Route {ROUTE_ID} to original headsign '{ORIGINAL_HEADSIGN}'...")
    
    response = table.get_item(Key={'PK': f"STOP_ROUTES#{STOP_ID}"})
    item = response.get('Item', {})
    routes = item.get('Routes', [])

    found_and_reverted = False
    new_routes_list = []
    for r in routes:
        if r.get('route_id') == ROUTE_ID:
            if r.get('headsign') != ORIGINAL_HEADSIGN:
                print(f"  Changing headsign from '{r.get('headsign')}' to '{ORIGINAL_HEADSIGN}'.")
                r['headsign'] = ORIGINAL_HEADSIGN
            new_routes_list.append(r)
            found_and_reverted = True
        else:
            new_routes_list.append(r)
    
    # If for some reason Route 1 was completely removed (shouldn't happen with my script), re-add it.
    if not found_and_reverted:
        print(f"  Route {ROUTE_ID} not found in list, adding it back with headsign '{ORIGINAL_HEADSIGN}'.")
        new_routes_list.append({'route_id': ROUTE_ID, 'headsign': ORIGINAL_HEADSIGN})

    table.put_item(Item={'PK': f"STOP_ROUTES#{STOP_ID}", 'Routes': new_routes_list})
    print(f"Successfully reverted STOP_ROUTES#{STOP_ID}.")

if __name__ == '__main__':
    revert_stop_routes_patch()
