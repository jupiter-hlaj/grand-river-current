# Grand River Current

**Grand River Current** is a high-performance, real-time bus tracking application for the Grand River Transit (GRT) system in the Region of Waterloo. It is designed to be lightweight, serverless, and extremely cost-effective, leveraging AWS Free Tier eligible services.

## 🚀 Features

- **Real-Time Tracking**: Visualizes bus locations with bearing/direction updates every 30 seconds.
- **Stop Lookups**: Search by stop ID to see stop location and details.
- **Optimized Data**: Uses binary GZIP compression for bus data in DynamoDB to minimize read/write costs.
- **Serverless Architecture**: Fully event-driven using AWS Lambda, DynamoDB, and CloudFront.
- **Static & Realtime Data**: Ingests both GTFS Static (schedules/stops) and GTFS Realtime (vehicle positions).

## 🏗 Architecture

The system is built on a "Serverless Microservices" pattern:

### 1. Ingestion Layer (`src/lambda/pkg_ingest`, `pkg_static`)
- **GRT_Ingest**: Triggers every minute (via EventBridge Scheduler). Fetches GTFS-Realtime Protobuf data from the GRT Open Data API, parses it, compresses the vehicle list into a GZIP binary blob, and saves it to DynamoDB.
- **GRT_Static_Ingest**: Runs on-demand or weekly. Downloads the huge GTFS Static ZIP, extracts `stops.txt`, and populates the DynamoDB table with stop coordinates and names.

### 2. Storage Layer (DynamoDB)
- **Table**: `GRT_Bus_State`
- **Data Model**:
  - `PK: BUS_ALL` -> Contains the latest compressed binary list of all active buses.
  - `PK: STOP#<stop_id>` -> Contains static details for a specific stop.

### 3. API Layer (`src/lambda/pkg_reader`)
- **GRT_Reader**: A read-only Lambda that serves as the backend API.
  - `GET /` -> Returns all bus positions (decompresses binary data from DB).
  - `GET /?stop_id=1234` -> Returns stop details.
  - `GET /?vehicle_id=999` -> Returns specific bus details.
- **CloudFront**: Acts as the "Shield" and CDN, caching API responses to reduce Lambda invocations and DynamoDB reads.

### 4. Frontend (`src/frontend`)
- A vanilla HTML/CSS/JS application using **Leaflet.js** for mapping.
- Hosted on S3 behind CloudFront for SSL and low latency.
- Polls the API every 15 seconds for bus updates.

## 📂 Project Structure

```
grand_river_current/
├── src/
│   ├── lambda/          # Python source code for Lambda functions
│   │   ├── pkg_ingest/  # Real-time data fetcher
│   │   ├── pkg_reader/  # API handler
│   │   ├── pkg_static/  # Static GTFS importer
│   │   └── ...
│   └── frontend/        # Web assets (index.html, css, js)
├── scripts/             # Deployment and maintenance scripts
├── infra/               # IAM policies and infrastructure config
├── tools/               # Utility scripts for debugging and data patching
└── requirements.txt     # Python dependencies
```

## 🛠 Deployment

The project includes a unified deployment script `scripts/setup_grand_river_current.sh` which handles:
1. Creating the S3 Bucket and DynamoDB Table.
2. Configuring IAM Roles and Policies.
3. generating the Python deployment packages.
4. Deploying Lambda functions.
5. Setting up the EventBridge Schedule.
6. configuring CloudFront.

*Note: If redeploying, ensure the script points to the correct source paths in `src/lambda`.*

## 🔗 APIs & Data Sources

- **GTFS Realtime**: `https://webapps.regionofwaterloo.ca/api/grt-routes/api/VehiclePositions`
- **GTFS Static**: `https://webapps.regionofwaterloo.ca/api/grt-routes/api/gtfs.zip`

## 📜 License
This project is for educational and portfolio purposes. Data is provided by the Region of Waterloo Open Data.
