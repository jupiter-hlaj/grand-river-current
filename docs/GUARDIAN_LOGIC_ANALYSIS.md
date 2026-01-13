# Low-Level Analysis: The "Guardian" (GRT_Update_Checker)

This document provides a technical deep dive into the code-level logic, heuristics, and state management of the `GRT_Update_Checker` Lambda function.

---

## 1. State Persistence & Detection Logic

The Guardian maintains its own "memory" to avoid redundant processing.

*   **Persistence Layer:** Uses DynamoDB with a specific record: `PK='CONFIG#STATIC'`.
*   **The Check:**
    1.  **HTTP HEAD Request:** The function sends a `HEAD` request to the GRT GTFS URL. This retrieves only the metadata (headers) without downloading the multi-megabyte file.
    2.  **Comparison:** It extracts the `Last-Modified` header and compares it to the `last_modified` value stored in DynamoDB.
    3.  **Short-Circuit:** If the values match, the function exits immediately with `NO_UPDATE_NEEDED`, consuming minimal memory and execution time.

---

## 2. Heuristic Validation Suite (`validate_gtfs`)

This is the core "intelligence" of the Guardian. It treats the incoming data as untrusted until proven otherwise through three layers of heuristics.

### Layer 1: Structural Integrity (The "Skeleton" Check)
*   **Logic:** The script opens the ZIP in-memory using `zipfile.ZipFile` and scans the file manifest (`namelist()`).
*   **Target:** `stops.txt`, `trips.txt`, `stop_times.txt`, and `calendar.txt`.
*   **Why:** If any of these are missing, the subsequent ingestion Lambdas will crash. This check prevents a "broken skeleton" from being accepted.

### Layer 2: Volume Verification (The "Empty File" Check)
*   **Logic:** It reads `stops.txt` and counts the newline-delimited rows.
*   **Heuristic Threshold:** `count < 2000`.
*   **Why:** A valid GRT dataset consistently contains ~2,500+ stops. A file with 50 stops is technically "valid" GTFS but logically "incorrect" for the Region of Waterloo. This check prevents a partial or empty dataset from overwriting the production database.

### Layer 3: Temporal Analysis (The "Time-Bomb" Check)
*   **Logic:** It parses the `calendar.txt` file, which defines the start and end dates of the transit schedule. It extracts the `end_date` from the first service record (Column 10).
*   **Heuristic Threshold:** `end_date < current_datetime`.
*   **Why:** Transit agencies sometimes release "historical" or "archival" feeds. If we load a schedule that expired yesterday, the app would show "No buses scheduled" for every stop. This check ensures the schedule is currently valid or represents a future service change.

---

## 3. Asynchronous Coordination & Execution

The Guardian does not perform the heavy lifting of database writes itself; it acts as a "Command and Control" center.

*   **Non-Blocking Triggers:** It uses `lambda_client.invoke` with `InvocationType='Event'`.
*   **The Chain:**
    1.  **Log:** It sends an `AutoUpdateStarted` event to `GRT_Logger`.
    2.  **Primary Ingest:** It triggers `GRT_Static_Ingest` to update stops and routes.
    3.  **Schedule Ingest:** It triggers `GRT_Static_Ingest_StopTimes` to update the millions of scheduled arrival times.
*   **Why:** By firing these as "Events," the Guardian can exit quickly while the heavy ingestion processes run in parallel in their own dedicated environments.

---

## 4. Error State & Logging Transitions

The Guardian is designed to "fail safe" and communicate its decisions.

| State | Internal Action | Log Action |
| :--- | :--- | :--- |
| **New File Detected** | Download & Validate | (None) |
| **Validation Failed** | Abort Update | `AutoUpdateBlocked` (with specific reason) |
| **Validation Passed** | Trigger Ingestions & Update DynamoDB Timestamp | `AutoUpdateStarted` |
| **Runtime Crash** | Exit | `AutoUpdateError` |

This logic ensures that you have a high-fidelity audit trail of why an update was applied or why it was safely rejected.
