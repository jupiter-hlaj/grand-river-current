import json, boto3, requests, time, os, datetime
from botocore.exceptions import ClientError

# Configuration
FRONTEND_URL = "http://grand-river-current-1767823978.s3-website-us-east-1.amazonaws.com"
API_URL = "https://dke47c3cr49qs.cloudfront.net"
LOGGER_URL = "https://q3racsvshuvureikmjutrb4fci0lsaom.lambda-url.us-east-1.on.aws/"
DYNAMO_TABLE = "GRT_Bus_State"
TEST_STOP_ID = "1001"

dynamodb = boto3.resource('dynamodb')
table = dynamodb.Table(DYNAMO_TABLE)

results = []

def add_result(category, test_name, status, message):
    results.append({
        "category": category,
        "test": test_name,
        "status": "✅ PASS" if status else "❌ FAIL",
        "message": message
    })
    print(f"[{'PASS' if status else 'FAIL'}] {category}: {test_name}")

def test_frontend():
    try:
        res = requests.get(FRONTEND_URL, timeout=10)
        success = (res.status_code == 200 and "Grand River Current" in res.text)
        add_result("Frontend", "S3 Web Hosting", success, f"Status: {res.status_code}")
    except Exception as e:
        add_result("Frontend", "S3 Web Hosting", False, str(e))

def test_api():
    try:
        start = time.time()
        res = requests.get(f"{API_URL}?stop_id={TEST_STOP_ID}", timeout=10)
        latency = round((time.time() - start) * 1000, 2)
        
        data = res.json()
        has_stop = "stop_details" in data
        has_buses = "nearby_buses" in data
        
        add_result("API", "Reader Response", (res.status_code == 200 and has_stop), f"Latency: {latency}ms")
    except Exception as e:
        add_result("API", "Reader Response", False, str(e))

def test_ingest_heartbeat():
    try:
        response = table.get_item(Key={'PK': 'BUS_ALL'})
        item = response.get('Item', {})
        updated_at = item.get('updated_at', 0)
        age_seconds = int(time.time()) - int(updated_at)
        
        # Ingest runs every 60s, so heartbeat should be < 120s
        success = (age_seconds < 120)
        add_result("Ingest", "Heartbeat (Live Data)", success, f"Data Age: {age_seconds}s")
    except Exception as e:
        add_result("Ingest", "Heartbeat (Live Data)", False, str(e))

def test_database_integrity():
    try:
        # Check for static stop data
        res = table.get_item(Key={'PK': f'STOP#{TEST_STOP_ID}'})
        has_stop = 'Item' in res
        
        # Check for static schedule data
        # (Using a known trip ID from previous logs if possible, or just checking for the prefix)
        res = table.scan(Limit=1, FilterExpression="begins_with(PK, :p)", ExpressionAttributeValues={':p': {"S": "TRIP_STOP_TIMES#"}})
        has_schedules = len(res.get('Items', [])) > 0
        
        add_result("Database", "Static Data Presence", (has_stop and has_schedules), f"Stops: {has_stop}, Schedules: {has_schedules}")
    except Exception as e:
        add_result("Database", "Static Data Presence", False, str(e))

def test_history_logging():
    try:
        # Look for a unique PK history record
        res = table.scan(
            Limit=1, 
            FilterExpression="begins_with(PK, :p)", 
            ExpressionAttributeValues={':p': {"S": "BUS_HISTORY#"}}
        )
        has_history = len(res.get('Items', [])) > 0
        add_result("History", "Unique Record Creation", has_history, "Found recent history blob" if has_history else "No history records found")
    except Exception as e:
        add_result("History", "Unique Record Creation", False, str(e))

def test_logger():
    try:
        payload = {"message": "SystemHealthCheck", "details": {"source": "AutomatedTestSuite"}}
        res = requests.post(LOGGER_URL, json=payload, timeout=10)
        add_result("Logger", "API Acceptance", (res.status_code == 202), f"Status: {res.status_code}")
    except Exception as e:
        add_result("Logger", "API Acceptance", False, str(e))

def generate_report():
    timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    report = f"# Grand River Current: System Health Report\n\n"
    report += f"**Timestamp:** {timestamp}\n\n"
    report += "| Category | Test | Status | Details |\n"
    report += "| :--- | :--- | :--- | :--- |\n"
    
    for r in results:
        report += f"| {r['category']} | {r['test']} | {r['status']} | {r['message']} |\n"
    
    with open("TEST_REPORT.md", "w") as f:
        f.write(report)
    print(f"\nReport generated: TEST_REPORT.md")

if __name__ == "__main__":
    print("Starting System Health Suite...\n")
    test_frontend()
    test_api()
    test_ingest_heartbeat()
    test_database_integrity()
    test_history_logging()
    test_logger()
    generate_report()
