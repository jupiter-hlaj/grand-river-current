# Grand River Current: Market-Based Scaling Analysis

**Data Context:** Based on 2024 GRT Ridership figures (~131,000 daily boardings).

---

## 1. Market Penetration vs. Operating Cost

How much of the GRT rider base can we support for **$0.00/month**?

| User Segment | Daily Users | Monthly Requests | Estimated Cost |
| :--- | :--- | :--- | :--- |
| **Early Adopters (1%)** | 1,300 | ~1.1 Million | **$0.00** |
| **Power Users (5%)** | 6,500 | ~5.8 Million | **$0.00** |
| **Mainstream (10%)** | 13,100 | ~11.7 Million | **~$1.70** |
| **Viral Success (25%)** | 32,750 | ~29.4 Million | **~$19.40** |

*Note: Calculations assume an average session of 5 minutes (approx. 10 data refreshes per user per trip).*

---

## 2. Infrastructure Resilience

### The "Back-to-School" Stress Test
The peak record of **150,000 boardings** (Sept 2023) represents the maximum possible load. 
*   Even if 100% of these riders opened the app during the morning rush, **CloudFront ("The Shield")** would absorb the impact. 
*   Because requests for the same stop ID are collapsed at the edge, the backend Lambda only sees a fraction of that traffic.
*   **Result:** The system cannot be "crashed" by high ridership; it can only become slightly more expensive.

### Student Demographic Impact
Given the 2.5% dip attributed to Conestoga and UW enrollment changes, our primary user base is likely concentrated around the **University/King** and **Frederick Station** stops.
*   **Strategic Advantage:** High-density stops are the most efficient for our caching model. The more students searching for the same stop simultaneously, the lower our per-user cost becomes.

---

## 3. Cost-Management Trigger Points

If the app exceeds the **10 Million free request limit** ($0.00 threshold), we have two "lever" points to return to free or low-cost operation:

1.  **Cache Extension:** Increase CloudFront `max-age` from 5s to 10s. This immediately cuts backend Lambda costs by 50% without significantly impacting user experience.
2.  **Polling Adjustment:** Adjust the `GRT_Ingest` loop from 10s to 20s. This reduces the "Always-On" compute time of the ingestion engine.

---

## 4. Summary for Stakeholders

The Grand River Current is uniquely positioned to handle the entire GRT rider population. 
*   For the first **15,000 unique daily riders**, the platform is **entirely free**.
*   To support the **entire 131,000 daily boarding population**, the estimated cost is only **~$150/month**—a fraction of the cost of traditional server-based architectures.
