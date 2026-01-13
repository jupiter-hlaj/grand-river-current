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

```mermaid
graph TD
    subgraph External_Data [External Data Sources]
        GRT_Realtime[GTFS Realtime API]
        GRT_Static[GTFS Static ZIP]
    end

    subgraph Ingestion_Layer [Ingestion Layer]
        EventBridge((EventBridge Scheduler))
        Ingest_Lambda[Lambda: GRT_Ingest]
        Static_Lambda[Lambda: GRT_Static_Ingest]
    end

    subgraph Storage_Layer [Storage Layer]
        DynamoDB[(DynamoDB: GRT_Bus_State)]
    end

    subgraph API_Layer [API Layer]
        Reader_Lambda[Lambda: GRT_Reader]
        CloudFront_API[CloudFront API Distribution]
    end

    subgraph Frontend_Layer [Frontend]
        S3_Bucket[S3 Bucket]
        CloudFront_Web[CloudFront Web Distribution]
        Browser[User Browser]
    end

    %% Flows
    EventBridge -->|Trigger 1/min| Ingest_Lambda
    GRT_Realtime -->|Protobuf| Ingest_Lambda
    Ingest_Lambda -->|Write GZIP| DynamoDB
    
    GRT_Static -->|Download| Static_Lambda
    Static_Lambda -->|Write Stops| DynamoDB

    Reader_Lambda -->|Read Binary| DynamoDB
    CloudFront_API -->|Request| Reader_Lambda
    Browser -->|Poll 15s| CloudFront_API
    
    S3_Bucket -->|Host| CloudFront_Web
    CloudFront_Web -->|Serve| Browser

    classDef aws fill:#FF9900,stroke:#232F3E,stroke-width:2px,color:white;
    classDef external fill:#EEEEEE,stroke:#333,stroke-dasharray: 5 5;
    
    class Ingest_Lambda,Static_Lambda,Reader_Lambda,DynamoDB,EventBridge,CloudFront_API,CloudFront_Web,S3_Bucket aws;
    class GRT_Realtime,GRT_Static external;
```

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

## 🛠 Manual Deployment Reference

*Legacy setup logic has been deprecated. Use the specifications below to configure AWS resources manually or via IaC.*

### 1. DynamoDB Table
- **Name**: `GRT_Bus_State`
- **Partition Key**: `PK` (String)
- **Capacity**: 25 RCU / 25 WCU (Provisioned)

### 2. IAM Roles
#### `GRT_Lambda_Role`
- **Trust Policy**: Allow `lambda.amazonaws.com`
- **Permissions**:
  - `AWSLambdaBasicExecutionRole`
  - `AmazonDynamoDBFullAccess`

#### `GRT_Scheduler_Role`
- **Trust Policy**: Allow `scheduler.amazonaws.com`
- **Permissions**: `lambda:InvokeFunction` on `GRT_Ingest` ARN.

### 3. Lambda Functions
*Runtime: Python 3.10 | Architecture: x86_64*

| Function Name | Code Source | Timeout | Environment Vars | Notes |
|---|---|---|---|---|
| `GRT_Ingest` | `src/lambda/pkg_ingest` | 60s | `DYNAMO_TABLE=GRT_Bus_State` | Triggered by EventBridge |
| `GRT_Static_Ingest` | `src/lambda/pkg_static` | 300s | `DYNAMO_TABLE=GRT_Bus_State` | Run manually/weekly |
| `GRT_Reader` | `src/lambda/pkg_reader` | 3s | `DYNAMO_TABLE=GRT_Bus_State` | Enable Function URL (Auth: NONE, CORS: *) |

### 4. EventBridge Schedule
- **Name**: `GRT_Ingest_Schedule`
- **Schedule**: `rate(1 minutes)`
- **Target**: `GRT_Ingest` Lambda
- **Role**: `GRT_Scheduler_Role`

### 5. CloudFront Distribution
- **Origin**: `GRT_Reader` Function URL (remove `https://`)
- **Origin Protocol Policy**: HTTPS Only
- **Viewer Protocol Policy**: Redirect HTTP to HTTPS
- **Cache Policy**: Caching Optimized (default)

## 🔗 APIs & Data Sources

- **GTFS Realtime**: `https://webapps.regionofwaterloo.ca/api/grt-routes/api/VehiclePositions`
- **GTFS Static**: `https://webapps.regionofwaterloo.ca/api/grt-routes/api/gtfs.zip`

## 📜 License
This project is for educational and portfolio purposes. Data is provided by the Region of Waterloo Open Data.
