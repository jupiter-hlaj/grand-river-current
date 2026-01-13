# Grand River Current: Historical Data Insights & Analysis

**Version:** 1.1
**Date:** January 8, 2026
**Data Source:** DynamoDB `GRT_Bus_State` table (PK: `BUS_HISTORY#timestamp`)

---

## 1. Overview of Data Collected

Every ~10-15 seconds, the `GRT_Ingest` Lambda captures a snapshot of all active bus locations and their metadata (ID, Lat/Lon, Bearing, Trip ID, Current Stop Sequence). This data is stored in DynamoDB using a unique Partition Key for each snapshot (`BUS_HISTORY#<timestamp>`). Items are set to automatically expire after 12 months (TTL).

This rich dataset enables retrospective analysis beyond real-time tracking, allowing for deeper insights into transit system performance and user experience.

---

## 2. Key Insights to Glean from Historical Data

### A. Route Performance & Reliability

1.  **On-Time Performance (OTP) by Route/Stop:**
    *   **Methodology:** Correlate `BUS_HISTORY` records (bus `timestamp` at `current_stop_sequence`) with `TRIP_STOP_TIMES` records (scheduled `arrival_time` for that stop sequence on that trip).
    *   **Analysis:** Calculate the average delay or earliness for specific routes at specific stops or across the entire route over different times of day (peak vs. off-peak), days of the week, or months.
    *   **Value:** Pinpoint specific routes or stops that consistently deviate from the schedule, enabling targeted operational improvements.

2.  **Dwell Time Analysis:**
    *   **Methodology:** For a given bus at a specific stop, calculate the duration it spends there by observing consecutive `BUS_HISTORY` records where the bus's `current_stop_sequence` remains the same or changes to the next sequence. This is an advanced analysis requiring interpolation.
    *   **Analysis:** Determine average waiting times at various stops.
    *   **Value:** Identify stops where buses spend unexpectedly long durations, which could indicate congestion, passenger loading issues, or schedule padding discrepancies.

### B. Ridership & Demand Patterns (Inferred)

1.  **Bus Bunching & Headway Consistency:**
    *   **Methodology:** Analyze `BUS_HISTORY` data for multiple buses on the same `route_id` over time. Calculate the time or distance between consecutive buses (headway).
    *   **Analysis:** Detect instances where buses on the same route are running too close together ("bunching") or where headways are inconsistent.
    *   **Value:** Understand operational issues leading to unreliable service, particularly during peak hours, and inform scheduling or dispatching strategies.

2.  **Speed & Congestion Mapping:**
    *   **Methodology:** For a single bus, calculate its average speed between two `current_stop_sequence` updates (`distance / time_difference`). Plot these speeds on a map or track them over time for specific road segments.
    *   **Analysis:** Identify areas of consistent congestion or unusually slow speeds across the network, even if real-time traffic data isn't available.
    *   **Value:** Inform urban planning decisions, identify bottlenecks, or suggest areas for dedicated bus infrastructure.

### C. Operational Insights & Quality Assurance

1.  **"Ghost Bus" Detection:**
    *   **Methodology:** Compare scheduled `TRIP_STOP_TIMES` entries for a given `trip_id` against its actual appearance in `BUS_HISTORY` records. 
    *   **Analysis:** Identify scheduled trips that consistently do not have a corresponding real-time bus location, indicating potential cancellations not reflected in the published schedule.
    *   **Value:** Improve schedule accuracy and identify operational gaps.

2.  **Off-Road Time & Maintenance Inference:**
    *   **Methodology:** Track individual bus IDs (`id`) in the `BUS_HISTORY`. If a bus is consistently missing from `BUS_HISTORY` during periods when it's typically active (e.g., during operational hours on a weekday) and not assigned to a specific trip, it suggests it's off-road.
    *   **Analysis:** Calculate the duration and frequency of such "off-road" periods for each vehicle. Correlate with any known maintenance schedules if available.
    *   **Value:** Gain insights into vehicle availability, maintenance cycles, and operational efficiency without needing direct maintenance logs.

3.  **Layover/Recovery Time Validation:**
    *   **Methodology:** Track a bus's `trip_id` from its final stop sequence to the start of its next trip. Measure the time elapsed at the terminus.
    *   **Analysis:** Assess if the allocated layover/recovery times in the schedule are adequate for drivers to reset and prepare for the next run, considering actual arrival delays.
    *   **Value:** Optimize schedules to improve reliability and driver well-being.

### D. Advanced Analytical Insights

1.  **System-Wide Health Metrics:**
    *   **Methodology:** At any given `timestamp` in `BUS_HISTORY`, analyze the entire fleet. Calculate the percentage of buses running on-time versus late, and the average delay for those that are late.
    *   **Analysis:** Generate high-level KPIs for the entire transit network's performance at any moment.
    *   **Value:** Provides a "mission control" overview for transit managers to spot system-wide issues (e.g., weather-related slowdowns) as they happen, rather than just seeing individual bus delays.

2.  **Delay Propagation Analysis:**
    *   **Methodology:** Track a single bus `trip_id` through its entire journey in `BUS_HISTORY`. Compare its on-time performance at the start, middle, and end of its route.
    *   **Analysis:** Determine if initial delays on a route tend to worsen (cascade) or resolve themselves due to schedule padding.
    *   **Value:** Informs schedulers which routes are resilient and which are prone to cascading failures, allowing for more robust schedule design.

3.  **Correlation with External Data (Weather & Events):**
    *   **Methodology:** Combine the historical on-time performance data with external datasets, such as historical weather records or city event calendars.
    *   **Analysis:** Quantify the impact of external factors on transit performance. For example: "A 5cm snowfall increases average system-wide delay by 12 minutes."
    *   **Value:** Enables proactive, data-driven operational planning, such as preemptively scheduling extra buses on days with forecasted heavy snow or major downtown events.

---

## 3. How to Access & Analyze the Data

1.  **AWS DynamoDB Console:** You can directly query the `GRT_Bus_State` table in the AWS Management Console. Filter by `PK = BUS_HISTORY` and use the `SK` (timestamp) to specify time ranges. The `buses_binary` field will contain the GZIP-compressed JSON snapshot.
2.  **AWS Data Export (Recommended for Advanced Analysis):** For in-depth analysis, you can periodically export your DynamoDB table to Amazon S3 (e.g., hourly or daily). From S3, the data can be queried using services like **Amazon Athena** (SQL on S3 data) or processed by tools like **AWS Glue** (ETL) for loading into a data warehouse like **Amazon Redshift**.
3.  **Local Processing:** Download the raw or exported JSON data and use programming languages (e.g., Python with Pandas) or specialized data analysis tools to decompress, parse, and analyze the historical bus movement patterns.

This historical data provides a powerful foundation for understanding and improving the Grand River Transit system.