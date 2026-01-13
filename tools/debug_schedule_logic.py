import boto3
import json

# This script assumes you have AWS credentials configured.
# It will connect to DynamoDB and fetch the raw schedule for a specific stop.

STOP_ID_TO_DEBUG = "1223"
ROUTE_ID_TO_DEBUG = "201" # As a string

def debug_schedule():
    """
    Fetches and prints the schedule for a specific stop and route from DynamoDB.
    """
    try:
        session = boto3.Session()
        dynamodb = session.resource('dynamodb')
        table = dynamodb.Table('GRT_Bus_State')

        pk = f"STOP_SCHEDULE#{STOP_ID_TO_DEBUG}"
        print(f"Querying DynamoDB for Partition Key: {pk}")

        response = table.get_item(Key={'PK': pk})
        
        if 'Item' not in response:
            print(f"Error: No schedule data found for stop {STOP_ID_TO_DEBUG}.")
            return

        item = response['Item']
        full_schedule = item.get('Schedule', [])
        
        print(f"\n--- Full Schedule for Stop {STOP_ID_TO_DEBUG} ---")
        print(f"Total entries: {len(full_schedule)}")

        route_201_schedule = [
            entry for entry in full_schedule 
            if str(entry.get('r')) == ROUTE_ID_TO_DEBUG
        ]

        if not route_201_schedule:
            print(f"\nNo schedule entries found for Route {ROUTE_ID_TO_DEBUG}.")
            return

        # Sort the results by time to see the correct order
        route_201_schedule.sort(key=lambda x: x.get('t', ''))

        print(f"\n--- Found {len(route_201_schedule)} entries for Route {ROUTE_ID_TO_DEBUG} (Sorted) ---")
        
        # Print the first and last 5 entries to get a sense of the service times
        print("\nFirst 5 departures:")
        for entry in route_201_schedule[:5]:
            print(f"  Time: {entry.get('t')}, Headsign: {entry.get('h')}")

        print("\nLast 5 departures:")
        for entry in route_201_schedule[-5:]:
            print(f"  Time: {entry.get('t')}, Headsign: {entry.get('h')}")

    except Exception as e:
        print(f"An error occurred: {e}")

if __name__ == '__main__':
    debug_schedule()
