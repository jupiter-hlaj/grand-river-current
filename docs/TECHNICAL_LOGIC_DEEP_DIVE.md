# Grand River Current: Technical Logic Deep Dive

This document explains the core logic patterns that allow "Grand River Current" to be highly accurate, fast, and free to operate.

---

## 1. The "Single-Item" Data Pattern (Cost Optimization)
Normally, tracking 200+ buses in a database would require 200+ individual read/write operations per refresh. In AWS, this would quickly exceed the Free Tier.

*   **The Logic:** The `GRT_Ingest` Lambda fetches the entire fleet, converts it to JSON, and then **GZIP compresses** it into a single binary blob. This blob is stored in a single DynamoDB item (`BUS_ALL`).
*   **The Result:** The `GRT_Reader` API can retrieve the entire state of the city's transit in **one single database read**. This reduces database costs by 99% and enables infinite scalability.

---

## 2. Smart Filtering (The "Loop" Problem)
Bus routes aren't straight lines; they are often loops. A simple "is the bus near the stop" check fails because a bus might be "near" a stop on its way *away* from it.

*   **The Logic:** The system uses `stop_sequence` instead of just GPS proximity.
    *   Every stop on a trip has a sequence number (e.g., 1 to 50).
    *   The `GRT_Reader` looks up the sequence number of *your* stop for that specific trip.
    *   It then compares it to the bus's `current_stop_sequence`.
    *   **Condition:** If `bus_sequence < stop_sequence`, the bus is approaching. If `bus_sequence >= stop_sequence`, the bus has already passed.
*   **The Result:** Users never see "Ghost" buses that are actually heading in the opposite direction or have already left the stop.

---

## 3. "Arrival Mode" (Latency Masking)
GPS data from buses is often delayed by 10-20 seconds. If the map auto-centers on a "lagging" GPS point just as the bus pulls up, the user experience feels "broken."

*   **The Logic:** The frontend monitors the "Stops Away" count.
*   **Trigger:** When `Stops Away <= 1`.
*   **The Action:** 
    1.  **Freeze Map:** Auto-panning is disabled. The map stays locked on the user's stop.
    2.  **UI Shift:** The countdown timer is replaced with a high-priority, pulsing **"DUE NOW"** badge.
*   **The Result:** By shifting the user's focus from the "lagging" map icon to the "imminent" UI badge, we provide a psychologically "real-time" experience that matches the physical arrival of the bus.

---

## 4. The "Guardian" (Heuristic AI Validation)
Automated updates are dangerous if the source data is corrupted.

*   **The Logic:** Before applying a new GTFS schedule, the `GRT_Update_Checker` runs a validation suite:
    *   **Structural:** Does the ZIP contain all 4 required files?
    *   **Volume:** Does it contain at least 2,000 stops? (Prevents loading "empty" files).
    *   **Temporal:** Is the "end date" of the schedule in the future? (Prevents loading expired schedules).
*   **The Result:** The system is "self-healing." It will refuse to update itself with bad data, keeping the last "known good" version active and logging a warning for review.

---

## 5. Edge-Cached Delivery (The "Shield")
A viral social media post could send 10,000 users to the app at once. A standard Lambda setup would crash or incur high costs.

*   **The Logic:** **AWS CloudFront** is configured with a 5-second "S-Maxage" cache policy.
*   **The Flow:** 
    1.  User A requests Stop 1001. CloudFront hits the Lambda, gets the data, and saves a copy.
    2.  User B requests Stop 1001 one second later. CloudFront serves the **saved copy** without ever talking to the backend.
*   **The Result:** The system can handle 100,000+ users as easily as 1 user, with the backend only "working" once every 5 seconds per stop.

---

## 6. Time-Travel History (Binary Archiving)
We wanted historical data without the storage cost of millions of rows.

*   **The Logic:** We use the same GZIP binary pattern for history. Each 12-second snapshot is saved as a single row with a `ttl` (Time to Live) attribute.
*   **The Result:** We store a year of "Time Travel" data (billions of GPS points) using only a few gigabytes of storage, all within the DynamoDB 25GB Free Tier.

---

## 7. Stop Schedule Indexing (Service Continuity)
Traditional GTFS APIs return "No data" when no buses are live. This is unhelpful for riders.

*   **The Logic:** The system indexes the entire static schedule city-wide into a "stop-centric" format (`STOP_SCHEDULE#stop_id`).
*   **The Execution:** When the `GRT_Reader` detects a route is offline, it queries this index to find the very next scheduled arrival time relative to the user's current time.
*   **The Result:** The app provides a seamless transition between live tracking and future planning, using friendly language like "Service resumes at 5:55 AM" instead of error messages.
