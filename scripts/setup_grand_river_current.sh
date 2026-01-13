#!/bin/bash
# Grand River Current v2.3 Deployment Script
# Features: Realtime + Static + GZIP + CLOUDFRONT (The Shield)
# Changes: Branding Updated to "Grand River Current"

# --- CONFIGURATION ---
MY_BUCKET_NAME="grand-river-current-$(date +%s)"
REGION="us-east-1"
ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)

echo "--- STARTING GRAND RIVER CURRENT INSTALLATION ---"
echo "Target Bucket: $MY_BUCKET_NAME"

# --- 1. INFRASTRUCTURE ---
echo "[1/8] Creating Core Infrastructure..."

# DynamoDB (Max Free Tier Capacity)
aws dynamodb create-table --table-name GRT_Bus_State \
   --attribute-definitions AttributeName=PK,AttributeType=S \
   --key-schema AttributeName=PK,KeyType=HASH \
   --provisioned-throughput ReadCapacityUnits=25,WriteCapacityUnits=25 > /dev/null 2>&1 || \
   aws dynamodb update-table --table-name GRT_Bus_State --provisioned-throughput ReadCapacityUnits=25,WriteCapacityUnits=25 > /dev/null 2>&1

# S3
aws s3 mb s3://$MY_BUCKET_NAME --region $REGION > /dev/null 2>&1 || echo "Bucket exists..."

# --- 2. IAM ROLES ---
echo "[2/8] Configuring IAM Policies..."
cat > trust.json <<EOF
{
  "Version": "2012-10-17", 
  "Statement": [ 
    { 
      "Effect": "Allow", 
      "Principal": { "Service": "lambda.amazonaws.com" }, 
      "Action": "sts:AssumeRole" 
    }, 
    {
      "Effect": "Allow", 
      "Principal": { "Service": "scheduler.amazonaws.com" }, 
      "Action": "sts:AssumeRole" 
    } 
  ] 
}
EOF

aws iam create-role --role-name GRT_Lambda_Role --assume-role-policy-document file://trust.json > /dev/null 2>&1
aws iam attach-role-policy --role-name GRT_Lambda_Role --policy-arn arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole
aws iam attach-role-policy --role-name GRT_Lambda_Role --policy-arn arn:aws:iam::aws:policy/AmazonDynamoDBFullAccess
echo "Waiting 10s for IAM propagation..."
sleep 10

# --- 3. GENERATE PYTHON CODE ---
echo "[3/8] Generating Application Logic..."
mkdir -p pkg_ingest pkg_reader pkg_static

# --- REALTIME INGEST CODE (GZIP) ---
cat > pkg_ingest/lambda_function.py << 'EOF'
import json, boto3, requests, time, os, gzip
from google.transit import gtfs_realtime_pb2
from boto3.dynamodb.types import Binary

URL = "https://webapps.regionofwaterloo.ca/api/grt-routes/api/VehiclePositions"
DYNAMO_TABLE = os.environ['DYNAMO_TABLE']
dynamodb = boto3.resource('dynamodb')
table = dynamodb.Table(DYNAMO_TABLE)

def fetch_and_save():
   try:
       response = requests.get(URL, timeout=10)
       if response.status_code != 200: return 0
       
       feed = gtfs_realtime_pb2.FeedMessage()
       feed.ParseFromString(response.content)
       
       bus_list = []
       timestamp = int(time.time())
       
       for entity in feed.entity:
           if entity.HasField('vehicle'):
               v = entity.vehicle
               bus_data = {
                   "id": v.vehicle.id,
                   "lat": round(v.position.latitude, 5),
                   "lon": round(v.position.longitude, 5),
                   "bearing": v.position.bearing,
                   "trip_id": v.trip.trip_id
               }
               bus_list.append(bus_data)
       
       if len(bus_list) < 10: return 0

       # Compression
       json_str = json.dumps(bus_list)
       compressed_data = gzip.compress(json_str.encode('utf-8'))

       item = {
           'PK': 'BUS_ALL',
           'updated_at': timestamp,
           'buses_binary': compressed_data,
           'count': len(bus_list)
       }
       table.put_item(Item=item)
       print(f"Updated {len(bus_list)} buses.")
       return len(bus_list)
   except Exception as e:
       print(f"Error: {e}")
       return 0

def lambda_handler(event, context):
   time.sleep(3)
   c1 = fetch_and_save()
   time.sleep(30)
   c2 = fetch_and_save()
   return {"status": "SUCCESS", "fetches": 2}
EOF

# --- STATIC INGEST CODE ---
cat > pkg_static/lambda_function.py << 'EOF'
import json, boto3, requests, os, io, zipfile, csv, time

STATIC_URL = "https://webapps.regionofwaterloo.ca/api/grt-routes/api/gtfs.zip"
DYNAMO_TABLE = os.environ['DYNAMO_TABLE']
dynamodb = boto3.resource('dynamodb')
table = dynamodb.Table(DYNAMO_TABLE)

def lambda_handler(event, context):
   print("Downloading Static GTFS...")
   r = requests.get(STATIC_URL)
   z = zipfile.ZipFile(io.BytesIO(r.content))
   
   with z.open('stops.txt') as f:
       reader = csv.DictReader(io.TextIOWrapper(f, 'utf-8'))
       count = 0
       with table.batch_writer() as writer:
           for row in reader:
               code = row.get('stop_code') or row.get('stop_id')
               if not code: continue
               item = {
                   'PK': f"STOP#{code}",
                   'lat': row.get('stop_lat'),
                   'lon': row.get('stop_lon'),
                   'name': row.get('stop_name'),
                   'type': 'STATIC_STOP'
               }
               writer.put_item(Item=item)
               count += 1
               if count % 50 == 0: time.sleep(0.2)
   return {"status": "SUCCESS", "stops_processed": count}
EOF

# ---READER CODE (GZIP) ---
cat > pkg_reader/lambda_function.py << 'EOF'
import json, boto3, os, gzip

DYNAMO_TABLE = os.environ['DYNAMO_TABLE']
dynamodb = boto3.resource('dynamodb')
table = dynamodb.Table(DYNAMO_TABLE)

def lambda_handler(event, context):
   try:
       params = event.get('queryStringParameters') or {}
       stop_id = params.get('stop_id')
       vehicle_id = params.get('vehicle_id')
       
       if stop_id:
           response = table.get_item(Key={'PK': f"STOP#{stop_id}"})
           item = response.get('Item')
           if not item: return response_proxy(404, {"error": "Stop not found"})
           return response_proxy(200, {
               "id": stop_id,
               "lat": float(item['lat']),
               "lon": float(item['lon']),
               "name": item['name']
           })
           
       response = table.get_item(Key={'PK': 'BUS_ALL'})
       item = response.get('Item')
       
       buses = []
       if item and 'buses_binary' in item:
           binary_data = item['buses_binary'].value
           json_str = gzip.decompress(binary_data).decode('utf-8')
           buses = json.loads(json_str)
       elif item and 'buses' in item:
           buses = json.loads(item['buses'])
       
       if vehicle_id:
           filtered = [b for b in buses if b['id'] == vehicle_id]
           if not filtered:
               return response_proxy(404, {"error": "Bus not active"})
           return response_proxy(200, filtered)
           
       return response_proxy(200, buses)
           
   except Exception as e:
       return response_proxy(500, {"error": str(e)})

def response_proxy(code, body):
   return {
       "statusCode": code,
       "headers": {
           "Access-Control-Allow-Origin": "*",
           "Content-Type": "application/json",
           "Cache-Control": "max-age=5" 
       },
       "body": json.dumps(body)
   }
EOF

# --- 4. DEPENDENCIES & ZIP ---
echo "[4/8] Installing Dependencies..."
pip install requests google-transit-gtfs-realtime-bindings protobuf -t pkg_ingest/ > /dev/null 2>&1
pip install requests -t pkg_static/ > /dev/null 2>&1

echo "Zipping packages..."
cd pkg_ingest && zip -r ../ingest.zip . > /dev/null 2>&1 && cd ..
cd pkg_static && zip -r ../static.zip . > /dev/null 2>&1 && cd ..
cd pkg_reader && zip -r ../reader.zip . > /dev/null 2>&1 && cd ..

# --- 5. DEPLOY LAMBDAS ---
echo "[5/8] Deploying Lambda Functions..."

aws lambda create-function --function-name GRT_Ingest --runtime python3.10 \
   --role arn:aws:iam::$ACCOUNT_ID:role/GRT_Lambda_Role \
   --handler lambda_function.lambda_handler --zip-file fileb://ingest.zip \
   --timeout 60 --environment "Variables={DYNAMO_TABLE=GRT_Bus_State}" > /dev/null 2>&1 || aws lambda update-function-code --function-name GRT_Ingest --zip-file fileb://ingest.zip > /dev/null 2>&1

aws lambda create-function --function-name GRT_Static_Ingest --runtime python3.10 \
   --role arn:aws:iam::$ACCOUNT_ID:role/GRT_Lambda_Role \
   --handler lambda_function.lambda_handler --zip-file fileb://static.zip \
   --timeout 300 --environment "Variables={DYNAMO_TABLE=GRT_Bus_State}" > /dev/null 2>&1 || aws lambda update-function-code --function-name GRT_Static_Ingest --zip-file fileb://static.zip > /dev/null 2>&1

aws lambda create-function --function-name GRT_Reader --runtime python3.10 \
   --role arn:aws:iam::$ACCOUNT_ID:role/GRT_Lambda_Role \
   --handler lambda_function.lambda_handler --zip-file fileb://reader.zip \
   --environment "Variables={DYNAMO_TABLE=GRT_Bus_State}" > /dev/null 2>&1 || aws lambda update-function-code --function-name GRT_Reader --zip-file fileb://reader.zip > /dev/null 2>&1

# Create Function URL (Direct access for CloudFront) 
RAW_READER_URL=$(aws lambda create-function-url-config --function-name GRT_Reader --auth-type NONE --cors '{"AllowOrigins": ["*"], "AllowMethods": ["GET"]}' --query FunctionUrl --output text)
# Strip https:// and trailing slash for CloudFront config
CF_ORIGIN=${RAW_READER_URL#https://}
CF_ORIGIN=${CF_ORIGIN%/}

# --- 6. SCHEDULE ---
echo "[6/8] Configuring Schedule..."
cat > scheduler_trust.json <<EOF
{
  "Version": "2012-10-17", 
  "Statement": [ 
    {
      "Effect": "Allow", 
      "Principal": { "Service": "scheduler.amazonaws.com" }, 
      "Action": "sts:AssumeRole" 
    } 
  ] 
}
EOF
aws iam create-role --role-name GRT_Scheduler_Role --assume-role-policy-document file://scheduler_trust.json > /dev/null 2>&1
aws iam put-role-policy --role-name GRT_Scheduler_Role --policy-name InvokeLambda --policy-document "{\"Version\":\"2012-10-17\",\"Statement\":[{\"Effect\":\"Allow\",\"Action\":\"lambda:InvokeFunction\",\"Resource\":\"arn:aws:lambda:$REGION:$ACCOUNT_ID:function:GRT_Ingest\"}]}" > /dev/null 2>&1
sleep 2

aws scheduler create-schedule --name GRT_Ingest_Schedule --schedule-expression "rate(1 minutes)" --target "{\"Arn\": \"arn:aws:lambda:$REGION:$ACCOUNT_ID:function:GRT_Ingest\", \"RoleArn\": \"arn:aws:iam::$ACCOUNT_ID:role/GRT_Scheduler_Role\"}" --flexible-time-window "{\"Mode\": \"OFF\"}" > /dev/null 2>&1

# --- 7. DEPLOY CLOUDFRONT (THE SHIELD) ---
echo "[7/8] Deploying CloudFront Shield..."
echo "Origin: $CF_ORIGIN"
# Simple Create Command
# Note: This creates a distribution with default settings (Caching Enabled)
CF_DOMAIN=$(aws cloudfront create-distribution \
   --origin-domain-name $CF_ORIGIN \
   --default-root-object "" \
   --query Distribution.DomainName \
   --output text)

echo "CloudFront deploying to: https://$CF_DOMAIN"

# --- 8. CONSOLE ---
echo "[8/8] Generating Console..."
cat > index.html <<EOF
<!DOCTYPE html>
<html>
<head>
   <title>Grand River Current</title>
   <link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css" />
   <script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
   <style>
       body{margin:0;padding:0;font-family:sans-serif;} 
       #map{height:100vh;width:100vw}
       #controls{position:absolute;top:10px;left:50px;z-index:999;background:white;padding:10px;border-radius:4px;box-shadow:0 0 10px rgba(0,0,0,0.2);}
       input{padding:5px;width:150px;} button{padding:5px;}
   </style>
</head>
<body>
   <div id="controls">
       <h3>Grand River Current</h3>
       <input type="text" id="stopId" placeholder="Enter Stop # (e.g. 2150)" />
       <button onclick="findStop()">Find Stop</button>
       <div id="status"></div>
   </div>
   <div id="map"></div>
   <script>
       // USE CLOUDFRONT URL
       const API_URL = 'https://$CF_DOMAIN';
       const map = L.map('map').setView([43.4503, -80.4832], 13);
       L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {attribution: '© OpenStreetMap'}).addTo(map);
       let busMarkers = {};
       let stopMarker = null;

       async function findStop() {
           const id = document.getElementById('stopId').value;
           document.getElementById('status').innerText = "Searching...";
           try {
               const res = await fetch(API_URL + "?stop_id=" + id);
               if (res.status === 404) { document.getElementById('status').innerText = "Not found."; return; }
               const data = await res.json();
               map.setView([data.lat, data.lon], 16);
               if (stopMarker) map.removeLayer(stopMarker);
               stopMarker = L.marker([data.lat, data.lon], {
                   icon: L.icon({
                       iconUrl: 'https://raw.githubusercontent.com/pointhi/leaflet-color-markers/master/img/markers-default/red-icon.png',
                       iconSize: [25, 41],
                       iconAnchor: [12, 41]
                   })
               }).addTo(map).bindPopup("<b>" + data.name + "</b><br>Stop #" + data.id).openPopup();
               document.getElementById('status').innerText = "";
           } catch (e) { document.getElementById('status').innerText = "Error."; }
       }

       async function fetchBuses() {
           try {
               const res = await fetch(API_URL);
               const buses = await res.json();
               const activeIds = new Set();
               
               buses.forEach(bus => {
                   activeIds.add(bus.id);
                   if (busMarkers[bus.id]) {
                       busMarkers[bus.id].setLatLng([bus.lat, bus.lon]);
                   } else {
                       const icon = L.divIcon({
                           className: 'bus-icon',
                           html: `<div style="transform: rotate(${bus.bearing}deg); font-size: 20px;">⬆️</div>`
                       });
                       busMarkers[bus.id] = L.marker([bus.lat, bus.lon], {icon: icon}).addTo(map).bindPopup('Bus ' + bus.id);
                   }
               });
               
               for (let id in busMarkers) {
                   if (!activeIds.has(id)) {
                       map.removeLayer(busMarkers[id]);
                       delete busMarkers[id];
                   }
               }
           } catch (e) { console.error("Error fetching buses"); }
       }
       
       fetchBuses();
       setInterval(fetchBuses, 15000);
   </script>
</body>
</html>
EOF

aws s3 cp index.html s3://$MY_BUCKET_NAME/index.html > /dev/null 2>&1
aws s3 website s3://$MY_BUCKET_NAME/ --index-document index.html > /dev/null 2>&1
aws s3api put-bucket-policy --bucket $MY_BUCKET_NAME --policy "{\"Version\":\"2012-10-17\",\"Statement\":[{\"Sid\":\"PublicRead\",\"Effect\":\"Allow\",\"Principal\":\"*\",\"Action\":\"s3:GetObject\",\"Resource\":\"arn:aws:s3:::$MY_BUCKET_NAME/*\"}]}" > /dev/null 2>&1

echo "--------------------------------------------------------"
echo "DEPLOYMENT SUCCESSFUL - GRAND RIVER CURRENT"
echo "API Endpoint (CloudFront): https://$CF_DOMAIN"
echo "Web Console: http://$MY_BUCKET_NAME.s3-website-$REGION.amazonaws.com"
echo "WARNING: CloudFront takes 10-15 minutes to activate. If you see errors, WAIT."