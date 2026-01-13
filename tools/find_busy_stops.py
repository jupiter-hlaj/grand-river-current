import boto3
import json

session = boto3.Session()
dynamodb = session.resource('dynamodb')
table = dynamodb.Table('GRT_Bus_State')

def find_busy():
    print("Scanning for busy stops...")
    scan = table.scan(
        FilterExpression='begins_with(PK, :s)', 
        ExpressionAttributeValues={':s': 'STOP_ROUTES#'},
        ProjectionExpression='PK, Routes'
    )
    
    stops = []
    for item in scan['Items']:
        count = len(item.get('Routes', []))
        if count > 3:
            stop_id = item['PK'].split('#')[1]
            stops.append((stop_id, count))
    
    # Sort by count desc
    stops.sort(key=lambda x: x[1], reverse=True)
    
    print("\n--- Top 10 Busiest Stops ---")
    for s_id, count in stops[:10]:
        # Get name
        name_resp = table.get_item(Key={'PK': f"STOP#{s_id}"})
        name = name_resp['Item'].get('name', 'Unknown') if 'Item' in name_resp else 'Unknown'
        print(f"Stop {s_id}: {count} routes - {name}")

if __name__ == '__main__':
    find_busy()
