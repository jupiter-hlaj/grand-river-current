import boto3
import os
import json
from collections import defaultdict

DYNAMO_TABLE = os.environ.get('DYNAMO_TABLE', 'GRT_Bus_State')
dynamodb = boto3.resource('dynamodb')
table = dynamodb.Table(DYNAMO_TABLE)

def lambda_handler(event, context):
    """
    Rebuilds the STOP_SCHEDULE lookup table by processing all TRIP_STOP_TIMES.
    This function is slow and memory-intensive, intended to be run infrequently.
    
    THE CRITICAL FIX is in this function: It sorts the schedule for each stop
    before writing it to the database, ensuring the GRT_Reader gets a pre-sorted list.
    """
    print("Starting rebuild of STOP_SCHEDULE index.")
    
    # In a real, large-scale system, you'd paginate this scan.
    # For GRT's data size, this is generally acceptable in a Lambda with sufficient memory/timeout.
    print("Scanning all TRIP_STOP_TIMES items...")
    response = table.scan(
        FilterExpression="begins_with(PK, :pk)",
        ExpressionAttributeValues={":pk": "TRIP_STOP_TIMES#"}
    )
    
    all_stop_times_items = response.get('Items', [])
    
    # Handle pagination if necessary
    while 'LastEvaluatedKey' in response:
        print(f"Paginating scan... Fetched {len(all_stop_times_items)} items so far.")
        response = table.scan(
            FilterExpression="begins_with(PK, :pk)",
            ExpressionAttributeValues={":pk": "TRIP_STOP_TIMES#"},
            ExclusiveStartKey=response['LastEvaluatedKey']
        )
        all_stop_times_items.extend(response.get('Items', []))

    print(f"Finished scan. Found {len(all_stop_times_items)} total trip schedules.")
    
    # Invert the data: map stop_id -> list of arrivals
    stops_to_schedule = defaultdict(list)

    print("Aggregating schedules by stop...")
    for item in all_stop_times_items:
        trip_id = item['PK'].split('#')[1]
        
        # We need to get the route_id and headsign for this trip
        trip_info_resp = table.get_item(Key={'PK': f"TRIP#{trip_id}"})
        if 'Item' not in trip_info_resp:
            continue
        
        route_id = trip_info_resp['Item'].get('route_id')
        headsign = trip_info_resp['Item'].get('headsign')

        if not route_id or not headsign:
            continue
            
        for stop_time in item.get('StopTimes', []):
            stop_id = stop_time.get('stop_id')
            arrival_time = stop_time.get('arrival_time')
            
            if stop_id and arrival_time:
                stops_to_schedule[str(stop_id)].append({
                    'r': route_id,
                    'h': headsign,
                    't': arrival_time
                })

    print(f"Aggregated data for {len(stops_to_schedule)} unique stops. Now sorting and writing to DB...")
    
    count = 0
    with table.batch_writer() as writer:
        for stop_id, schedule_list in stops_to_schedule.items():
            
            # *** THE CRITICAL FIX: Sort the schedule chronologically before writing ***
            sorted_schedule = sorted(schedule_list, key=lambda x: x['t'])
            
            writer.put_item(
                Item={
                    'PK': f"STOP_SCHEDULE#{stop_id}",
                    'Schedule': sorted_schedule
                }
            )
            count += 1
            if count % 100 == 0:
                print(f"Wrote {count} sorted schedules to DynamoDB...")

    print(f"Finished. Wrote {count} sorted schedules to STOP_SCHEDULE index.")
    return {'statusCode': 200, 'body': json.dumps('STOP_SCHEDULE rebuild complete.')}
