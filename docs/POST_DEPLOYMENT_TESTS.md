# Grand River Current: Post-Deployment Verification Plan

**Version:** 1.0
**Date:** January 7, 2026

## 1. Introduction
This document outlines the standard verification tests to be performed after any modification or deployment to the Grand River Current system. The goal is to provide a quick, repeatable process to ensure that all core components are functioning correctly, from data ingestion to the end-user-facing map.

## 2. Prerequisites
Before starting, you will need:
*   The AWS CLI installed and configured.
*   The **Web Console URL** (e.g., `http://grand-river-current-xxxxxxxxxx.s3-website-us-east-1.amazonaws.com`).
*   The **API Endpoint URL** (e.g., `https://d12345.cloudfront.net`).

---

## 3. Manual Verification (Browser)
These tests should be performed in a browser, preferably in an incognito or private window to avoid cache issues.

### Test 1: Web Console Accessibility
1.  **Action:** Open the **Web Console URL** in your browser.
2.  **Expected Result:** The map interface loads successfully. You should see the "Grand River Current" title, a map centered on the Waterloo Region, and a search box. The status message should indicate it is loading or has loaded live data.
3.  **Failure Indicates:** An issue with S3 bucket permissions, S3 static website configuration, or DNS.

### Test 2: Live Bus Data Verification
1.  **Action:** With the web console open, wait approximately 15-20 seconds.
2.  **Expected Result:** Bus icons (⬆️) should appear on the map. The status text should update to show the number of active buses and the last update time (e.g., "150 buses active. Last updated: 10:30:00 PM").
3.  **Failure Indicates:**
    *   A problem with the `GRT_Ingest` Lambda (not fetching data).
    *   An issue with the `GRT_Reader` Lambda (not reading from DynamoDB).
    *   A CORS or connectivity problem between the browser and the CloudFront API endpoint. Check the browser's developer console (F12) for errors.

### Test 3: Stop Search Functionality
1.  **Action:** In the "Enter Stop #" input box, type a known, valid stop number (e.g., `2150` or `2329`) and click "Find Stop".
2.  **Expected Result:** The map view zooms in to the specific stop's location, and a red marker appears with the stop name and number in a popup. The status message updates to "Stop [ID] found."
3.  **Failure Indicates:**
    *   An issue with the `GRT_Static_Ingest` Lambda (stop data was not loaded).
    *   A problem with the `GRT_Reader` Lambda's logic for handling `stop_id` queries.
    *   CloudFront is not correctly forwarding query string parameters to the Lambda origin.

---

## 4. Automated Verification (AWS CLI)
These tests verify the backend infrastructure directly.

### Test 4: Data Ingestion Check
1.  **Action:** Run the following command to check for recently ingested data in DynamoDB.
    ```bash
    aws dynamodb get-item --table-name GRT_Bus_State --key '{"PK": {"S": "BUS_ALL"}}' --attributes-to-get "updated_at" "count"
    ```
2.  **Expected Result:** The command returns a JSON object containing the `Item` key. Inside, you should see `updated_at` (a recent Unix timestamp) and `count` (a number greater than 0).
3.  **Failure Indicates:** The `GRT_Ingest` Lambda or the EventBridge Scheduler (`GRT_Ingest_Schedule`) is failing. Check the Lambda's CloudWatch logs.

### Test 5: API Endpoint Health Check
1.  **Action:** Run a `curl` command to test the CloudFront API endpoint directly.
    ```bash
    curl -I https://<YOUR_CLOUDFRONT_DOMAIN_HERE>
    ```
    *Replace `<YOUR_CLOUDFRONT_DOMAIN_HERE>` with your actual API Endpoint URL.*
2.  **Expected Result:** You should receive an `HTTP/2 200` status code. The headers should include `Content-Type: application/json` and `Cache-Control: max-age=5, public`.
3.  **Failure Indicates:**
    *   **504 (Gateway Timeout):** A configuration issue between CloudFront and the Lambda Function URL (check Origin Protocol Policy, Lambda permissions).
    *   **403 (Forbidden):** The Lambda Function URL is missing the necessary resource-based policy to allow public invocation.
    *   Other errors may point to issues with the `GRT_Reader` Lambda itself. Check its CloudWatch logs.

### Test 6: API Stop Search Test (CLI)
1.  **Action:** Run a `curl` command to test the stop search functionality via the API.
    ```bash
    curl "https://<YOUR_CLOUDFRONT_DOMAIN_HERE>?stop_id=2150"
    ```
2.  **Expected Result:** The command returns a JSON object with the details for stop #2150, including `id`, `lat`, `lon`, and `name`.
    ```json
    {"id": "2150", "lat": "43.443118", "lon": "-80.520428", "name": "UNIVERSITY AVE. / SEAGRAM"}
    ```
3.  **Failure Indicates:** CloudFront is not forwarding query strings, or the `GRT_Reader` Lambda has an issue with its stop search logic.
