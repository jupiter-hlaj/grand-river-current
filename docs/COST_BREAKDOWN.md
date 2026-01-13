# Grand River Current: Cost & Scalability Analysis

**Version:** 2.0 (Post-High Frequency Polling Update)
**Date:** January 8, 2026
**Target Operating Cost:** $0.00 / month

---

## 1. Monthly AWS Free Tier Usage (Estimates)

The system is architected to stay within the "Always Free" and "12-Month Free" tiers of AWS.

| Service | Metric | System Consumption | Free Tier Limit | % Used |
| :--- | :--- | :--- | :--- | :--- |
| **CloudFront** | Requests | ~2.5 Million | 10 Million | 25% |
| **CloudFront** | Data Out | ~25 GB | 1,000 GB (1TB) | 2.5% |
| **Lambda** | Compute (GB-s) | ~275,000 | 400,000 | 68% |
| **Lambda** | Requests | ~250,000 | 1,000,000 | 25% |
| **DynamoDB** | Write Capacity | ~0.1 WCU | 25 WCU | <1% |
| **DynamoDB** | Read Capacity | ~2 RCU | 25 RCU | 8% |
| **DynamoDB** | Storage | ~150 MB | 25 GB | <1% |
| **S3** | Storage | ~1 MB | 5 GB | <1% |

---

## 2. User Capacity & Concurrency

The **"Shield" (CloudFront Caching)** is the reason this app can support thousands of users for free. Because we cache API responses for 5 seconds, the backend database never sees the actual "load" of the users.

### "How many people can use this at once?"

We define "Concurrent Users" as people having the app open and active at the same second.

#### A. The 24/7 Baseline
If users were active 24 hours a day, 7 days a week, the **CloudFront Request Limit (10M/month)** is the primary bottleneck.
*   **Capacity:** **~115 users** can have the app open **24/7** for the entire month without costing a cent.

#### B. The Real-World Peak (The Commuter Spike)
In reality, transit apps see massive spikes during morning and afternoon rushes.
*   **Peak Capacity:** You can support **~1,200 concurrent users** during a 2-hour rush period every single day.
*   **Total Monthly Users:** Approximately **15,000 unique riders** can use the app for 15 minutes a day, every day, entirely for free.

---

## 3. Technical Bottlenecks

### 1. Ingestion Duration (The "Loop")
The recent update to 10-second polling increased the `GRT_Ingest` Lambda's duration to 50 seconds per minute.
*   **Limit:** This uses up ~270,000 of your 400,000 free GB-seconds.
*   **Action:** If you ever exceed the free tier, we simply reduce the polling from 10s back to 20s or 30s to cut the "billable" compute time in half instantly.

### 2. DynamoDB Throughput
While we increased the table limit to 100 WCU for the initial "heavy" static ingestion, the day-to-day real-time ingestion only uses ~6 writes per minute.
*   **Safety:** The system is currently configured at **100 WCU**. To ensure it stays "Always Free" long-term, this can be lowered back to **25 WCU** now that the initial data load is complete.

---

## 4. Scaling Beyond Free Tier

If the app becomes so popular that you exceed 10 million requests per month:
1.  **Cost:** AWS starts charging roughly **$1.00 per million requests**.
2.  **Performance:** There is no performance degradation. CloudFront and Lambda will scale automatically to handle millions of users; the only change is a very small incremental cost.

**Summary:** For a local transit tool, the current architecture is virtually impossible to "break" with standard user traffic, and the cost will remain **$0.00** for the foreseeable future.
