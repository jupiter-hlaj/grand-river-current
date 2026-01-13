# Grand River Current: Project Summary

**Date:** January 8, 2026
**Status:** Live & Operational

---

## 1. Project Goal

The objective was to develop a highly scalable, cost-effective, and user-friendly mobile web application for tracking Grand River Transit (GRT) buses in real-time. The primary focus was on providing a rider-centric experience that is faster and more accurate than generic mapping applications, while operating entirely within the AWS Free Tier.

---

## 2. Final Architecture & Technology

The project successfully implemented a **serverless, edge-cached architecture** designed for massive concurrency and zero operational cost.

*   **Frontend:** A responsive, mobile-first single-page application (`index.html`) hosted on **Amazon S3**.
*   **API & Caching:** **AWS CloudFront** acts as a global CDN, caching API responses for 5 seconds to absorb user load. This is the "secret sauce" that allows the system to scale.
*   **Backend Logic:** A suite of **AWS Lambda** functions written in Python handle data ingestion and API requests.
    *   `GRT_Ingest`: Fetches live bus data every ~15 seconds.
    *   `GRT_Static_Ingest` & `GRT_Static_Ingest_StopTimes`: Process static GTFS schedule data (routes, stops, times).
    *   `GRT_Reader`: The smart API that filters, enriches, and serves data to the user.
*   **Database:** **Amazon DynamoDB** stores all real-time and static data, including a rolling 12-month historical archive of bus movements.
*   **Scheduling:** **Amazon EventBridge** triggers the ingestion Lambda every minute.

---

## 3. Key Features Implemented

*   **Live Bus Tracking:** Displays bus locations on an interactive map, updated with high frequency.
*   **Stop-Centric Search:** Users can search for a specific stop number to see all relevant, approaching buses.
*   **Intelligent Filtering:**
    *   Automatically filters out buses that have already passed the user's stop.
    *   Correctly handles routes with loops to show the *next* valid arrival.
*   **Schedule Integration:** Displays the "Next Scheduled Arrival" time for each bus.
*   **"Arrival Mode":** When a bus is one stop away, the UI switches to a "DUE NOW" state and freezes the map to provide a smooth final-approach experience, masking any data latency.
*   **Service Continuity:** When buses are offline (e.g., late at night), the app provides the exact time service resumes (e.g., "Service resumes at 5:45 AM") by querying a specialized stop-schedule index.
*   **Historical Data Logging:** All bus movements are archived for 12 months for free, enabling advanced performance and reliability analysis.
*   **Polished Mobile UI:** Includes a custom CSS bus icon, refined shadow effects for a "floating" feel, and numerous UX micro-interactions like auto-selecting single routes and automatic keyboard dismissal.

---

## 4. Operational Links

*   **Live Application:** [http://grand-river-current-1767823978.s3-website-us-east-1.amazonaws.com](http://grand-river-current-1767823978.s3-website-us-east-1.amazonaws.com)
*   **API Endpoint:** [https://dke47c3cr49qs.cloudfront.net](https://dke47c3cr49qs.cloudfront.net)

---

## 5. Outcome

The "Grand River Current" project is a complete success. It is a production-ready, highly reliable application that meets all initial goals. It can support the entire GRT ridership base with minimal to zero monthly cost, while providing a feature-rich, user-friendly experience. The addition of historical data logging transforms the tool from a simple tracker into a powerful transit analysis platform with significant future potential.