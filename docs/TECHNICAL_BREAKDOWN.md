# Grand River Current: Technical Breakdown

## Recent Stability Fixes (Jan 2026)

The application underwent a significant refactor to improve stability, maintainability, and user experience after encountering several edge cases related to real-time data discrepancies at terminal stops.

### 1. Code Refactoring

The monolithic `index.html` file became difficult to manage. The application was refactored into a modular structure:
-   **`index.html`**: The main application shell.
-   **`css/style.css`**: All styling and animations.
-   **`js/app.js`**: All application logic, map handling, and API calls.

This separation of concerns makes debugging and future development significantly easier.

### 2. Backend Logic Simplification (`GRT_Reader`)

Initial attempts to implement complex "Terminal Turnover" logic using `block_id` and heuristics led to instability and bugs. The final, stable backend logic is much simpler and more robust:

-   **Primary Filter**: The `GRT_Reader` filters live buses based on whether they are scheduled to visit the requested `stop_id`.
-   **GPS Drift Buffer**: A small buffer (`+1` stop sequence) was added to the filter. This prevents buses from disappearing from the map prematurely if their GPS data updates slightly before they have fully departed a stop.
-   **Reliable Fallbacks**: If a live bus cannot be found for a route, the system reliably falls back to showing the next scheduled departure time from the static GTFS data. All complex heuristics were removed in favor of this predictable behavior.

### 3. Frontend UI/UX Enhancements

Several UI bugs and inconsistencies were resolved:

-   **State Persistence**: The route list no longer shrinks or loses "Scheduled" routes when navigating back from the tracking view. The full API response is now cached in a `lastApiData` variable.
-   **Clearer Terminology**: Ambiguous terms like "Done" were replaced with clearer transit-oriented language like **"Final Stop"**. The styling for "Final Stop" was also corrected to be a neutral grey, not an active blue.
-   **Smoother Animations**: Harsh blinking animations for "Due Now" were replaced with a softer, pulsating "breathe" effect for a more polished feel.

### 4. Solved: The Terminal Turnover Problem (Hybrid Bus Model)

A significant challenge was accurately displaying bus information at terminal stops where a bus arrives on one route and immediately turns over to depart on a different route. Users could physically see a bus, but the app would only show a future "Scheduled" departure.

-   **Problem:** At "Frederick Station" (Stop 1000), a user waiting for "Route 4 The Boardwalk" could see the bus arriving as "Route 4 Frederick Station," but the app would not track it, as its destination didn't match the departing route list.
-   **Solution:** A **"Hybrid Bus" model** was implemented in the `GRT_Reader` Lambda.
    1.  The system identifies the next *scheduled departure time* for the user's chosen route (e.g., 09:25 for "4 The Boardwalk").
    2.  It then scans the list of otherwise ignored live buses. Using a heuristic (matching route number and the bus's destination name matching the current stop's name), it finds the physically present *incoming* bus.
    3.  It creates a **hybrid object** for the frontend, combining the **live GPS data** (ID, lat, lon) from the incoming bus with the **scheduled departure time** of the user's chosen route.
-   **Outcome:** The user now sees the correct, live-tracked bus on the map while also being shown the accurate scheduled departure time for their journey. This provides a seamless and intuitive experience that matches real-world observations.

This series of reverts and refinements has resulted in a more stable and predictable user experience, now capable of handling complex terminal turnover scenarios. The current architecture prioritizes reliability and data accuracy based on the official GRT feeds.

---
_Original documentation follows_
---

# Grand River Current: Technical Architecture & Operational Guide

**Version:** 1.4
**Date:** January 8, 2026
**System Status:** Production Ready (v2.6)

---

## 1. Technology Stack & Rationale

The system is designed as a **serverless, edge-cached application** optimized for high concurrency, zero maintenance, and AWS Free Tier eligibility.

### Core Components

| Technology | Role | Justification |
| :--- | :--- | :--- |
| **AWS CloudFront** | **"The Shield" / CDN** | **Critical.** Caches API responses for 5 seconds. Ensures scalability and protects the backend from traffic spikes. |
| **AWS Lambda** | **Serverless Compute** | Handles logic on-demand. Separate functions for Ingest, Reading, Logging, and Maintenance. |
| **AWS DynamoDB** | **NoSQL Database** | High-performance storage for live states, static schedules, and historical archives. |
| **Amazon S3** | **Hosting & Storage** | Hosts the static frontend and stores raw GTFS assets. |
| **Amazon EventBridge** | **Scheduler** | Automates live data ingestion (every 1m) and static data health checks (weekly). |

---

## 2. Backend Function Breakdown

### A. `GRT_Ingest` (Real-Time Ingestion)
*   **Purpose:** Fetches live bus positions every ~12 seconds.
*   **Logic:** Compresses fleet data into a single `BUS_ALL` item and archives snapshots as unique `BUS_HISTORY#timestamp` items.

### B. `GRT_Static_Ingest` (Infrastructure Ingestion)
*   **Purpose:** Processes basic GTFS static data (Stops, Routes, Trips).

### C. `GRT_Static_Ingest_StopTimes` (Schedule Ingestion)
*   **Purpose:** Processes the raw, massive trip schedule (Millions of rows).

### D. `GRT_Static_Ingest_StopSchedule` (Service Continuity Indexer)
*   **Purpose:** Builds a stop-centric schedule index for after-hours accuracy.
*   **Logic:** Re-organizes trip data into `STOP_SCHEDULE#<id>` items. Each contains a sorted list of every arrival at that stop for the day. This allows for near-instant lookup of the "Next Bus" without scanning millions of rows.

### E. `GRT_Reader` (The API)
*   **Purpose:** Serves live and scheduled data to the frontend.
*   **Smart Logic:**
    1.  **Live Filter:** Identifies buses currently approaching the stop.
    2.  **Continuity Fallback:** If a route has no live buses, it queries the `STOP_SCHEDULE` index to find the next valid arrival time.

### F. `GRT_Logger` (User Activity Logging)
*   **Purpose:** Captures asynchronous usage logs for analysis.

### G. `GRT_Update_Checker` (The Automated Guardian)
*   **Purpose:** Weekly check for GTFS updates with heuristic validation.

---

## 3. Workflow: "Where is my bus?"

**Scenario:** A user searches for a stop at 11:30 PM (End of service).

1.  **Frontend:** Calls API for `stop_id`.
2.  **API (`GRT_Reader`):**
    *   Finds 0 live buses for the stop.
    *   Queries `STOP_SCHEDULE#<id>`.
    *   Finds first arrival tomorrow at 5:55 AM.
3.  **UI Visualization:**
    *   Displays route cards with dashed borders (indicating "waiting" state).
    *   Shows friendly message: **"Service resumes tomorrow at 5:55 AM"**.

---

## 5. Maintenance & Operations

*   **Automated Updates:** Managed by `GRT_Update_Checker`.
*   **Manual Trigger:** `GRT_Static_Ingest_StopSchedule` should be run manually (or via the Guardian) whenever a major schedule change occurs to rebuild the stop-centric index.
*   **Cost Control:** Entirely AWS Free Tier compatible.
