import json, boto3, requests, os, zipfile, io, datetime
from botocore.exceptions import ClientError

# Configuration
GTFS_URL = "https://webapps.regionofwaterloo.ca/api/grt-routes/api/GTFS"
DYNAMO_TABLE = os.environ['DYNAMO_TABLE']
INGEST_FUNCTION = "GRT_Static_Ingest"
STOP_TIMES_FUNCTION = "GRT_Static_Ingest_StopTimes"

dynamodb = boto3.resource('dynamodb')
table = dynamodb.Table(DYNAMO_TABLE)
lambda_client = boto3.client('lambda')

def log_to_system(message, details=None):
    """Sends a log to our central GRT_Logger"""
    try:
        # We invoke the logger directly to save on HTTP overhead
        lambda_client.invoke(
            FunctionName="GRT_Logger",
            InvocationType='Event',
            Payload=json.dumps({"body": json.dumps({"message": message, "details": details or {}})})
        )
    except: pass

def get_last_modified():
    try:
        response = table.get_item(Key={'PK': 'CONFIG#STATIC'})
        return response.get('Item', {}).get('last_modified', "")
    except: return ""

def update_last_modified(new_val):
    table.put_item(Item={'PK': 'CONFIG#STATIC', 'last_modified': new_val, 'updated_at': datetime.datetime.utcnow().isoformat()})

def validate_gtfs(content):
    """The 'Guardian' Heuristic Validation Logic"""
    try:
        with zipfile.ZipFile(io.BytesIO(content)) as z:
            files = z.namelist()
            required = ['stops.txt', 'trips.txt', 'stop_times.txt', 'calendar.txt']
            
            # 1. Structural Check
            for f in required:
                if f not in files: return False, f"Missing required file: {f}"
            
            # 2. Volume Check (Heuristic: GRT always has > 2000 stops)
            stops_count = len(z.read('stops.txt').decode('utf-8').splitlines())
            if stops_count < 2000: return False, f"Suspiciously low stop count: {stops_count}"
            
            # 3. Date Check (Heuristic: Ensure schedule isn't expired)
            calendar_lines = z.read('calendar.txt').decode('utf-8').splitlines()
            if len(calendar_lines) > 1:
                # Get the end_date from the second line (first is header)
                # Format is usually YYYYMMDD
                end_date_str = calendar_lines[1].split(',')[9] 
                end_date = datetime.datetime.strptime(end_date_str, '%Y%m%d')
                if end_date < datetime.datetime.now():
                    return False, f"Schedule expired on {end_date_str}"

        return True, "Validation Passed"
    except Exception as e:
        return False, str(e)

def lambda_handler(event, context):
    try:
        # 1. Check for updates
        head = requests.head(GTFS_URL)
        new_last_modified = head.headers.get('Last-Modified')
        
        old_last_modified = get_last_modified()
        
        if new_last_modified == old_last_modified and old_last_modified != "":
            print("No new data found.")
            return {"status": "NO_UPDATE_NEEDED"}

        # 2. New data found, download and validate
        print(f"New data detected ({new_last_modified}). Downloading for validation...")
        res = requests.get(GTFS_URL)
        is_valid, reason = validate_gtfs(res.content)
        
        if not is_valid:
            log_to_system("AutoUpdateBlocked", {"reason": reason, "header": new_last_modified})
            return {"status": "INVALID_DATA", "reason": reason}

        # 3. Trigger ingestions
        print("Data validated. Triggering re-ingestion...")
        log_to_system("AutoUpdateStarted", {"header": new_last_modified})
        
        # Trigger Static Ingest
        lambda_client.invoke(FunctionName=INGEST_FUNCTION, InvocationType='Event')
        # Trigger Stop Times (This one takes a while, so we just fire and forget)
        lambda_client.invoke(FunctionName=STOP_TIMES_FUNCTION, InvocationType='Event')
        
        update_last_modified(new_last_modified)
        
        return {"status": "UPDATE_TRIGGERED", "version": new_last_modified}

    except Exception as e:
        log_to_system("AutoUpdateError", {"error": str(e)})
        return {"status": "ERROR", "message": str(e)}
