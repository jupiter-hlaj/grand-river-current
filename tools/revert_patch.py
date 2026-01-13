import boto3
import json
import os

# Configure AWS
session = boto3.Session()
dynamodb = session.resource('dynamodb')
table = dynamodb.Table('GRT_Bus_State')

def revert_stop_1000():
    stop_id = '1000'
    print(f"Reverting Stop {stop_id} routes...")

    resp = table.get_item(Key={'PK': f"STOP_ROUTES#{stop_id}"})
    if 'Item' not in resp: return
    
    routes = resp['Item'].get('Routes', [])
    
    # Remove Route 4 (Frederick Station)
    original_len = len(routes)
    routes = [r for r in routes if not (r['route_id'] == '4' and r['headsign'] == 'Frederick Station')]
    
    if len(routes) < original_len:
        print("Removing Route 4 (Frederick Station)...")
        table.update_item(
            Key={'PK': f"STOP_ROUTES#{stop_id}"},
            UpdateExpression="SET #r = :r",
            ExpressionAttributeNames={'#r': 'Routes'},
            ExpressionAttributeValues={':r': routes}
        )
        print("Revert successful.")
    else:
        print("Route not found, nothing to revert.")

if __name__ == '__main__':
    revert_stop_1000()
