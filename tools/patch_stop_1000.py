import boto3
import json
import os
from decimal import Decimal

# Configure AWS
session = boto3.Session()
dynamodb = session.resource('dynamodb')
table = dynamodb.Table('GRT_Bus_State')

def patch_stop_1000():
    stop_id = '1000'
    print(f"Patching Stop {stop_id} routes...")

    # Get current routes
    resp = table.get_item(Key={'PK': f"STOP_ROUTES#{stop_id}"})
    if 'Item' not in resp:
        print("Error: STOP_ROUTES not found.")
        return
    
    item = resp['Item']
    routes = item.get('Routes', [])
    
    # Check if target route exists
    target = {'route_id': '4', 'headsign': 'Frederick Station'}
    exists = any(r['route_id'] == target['route_id'] and r['headsign'] == target['headsign'] for r in routes)
    
    if exists:
        print("Route 4 (Frederick Station) already exists. No patch needed.")
    else:
        print("Adding Route 4 (Frederick Station)...")
        routes.append(target)
        
        # Write back to DynamoDB
        table.update_item(
            Key={'PK': f"STOP_ROUTES#{stop_id}"},
            UpdateExpression="SET #r = :r",
            ExpressionAttributeNames={'#r': 'Routes'},
            ExpressionAttributeValues={':r': routes}
        )
        print("Patch successful!")

if __name__ == '__main__':
    patch_stop_1000()
