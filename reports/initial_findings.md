# Marketlytics: evidence-based EDA findings (draft)

Generated: 2026-11-05T09:00:54.873497+00:00

## Scope and metric definitions

- Item revenue is the sum of source order-item `price`; freight is calculated separately.
- AOV divides item revenue by orders with at least one item row (98,666 in this extract).
- Repeat rate and RFM use delivered orders and stable `customer_unique_id`; frequency is based on distinct delivered orders.
- On-time delivery is calculated for delivered orders with both actual and estimated delivery dates.
- MoM figures are emitted only when both months have at least 100 item orders and at least 95% item-order coverage.
- These are descriptive public-data measures; they do not establish causality or profit.

## Measured results

- Recorded item revenue is **13,591,643.70** source units; freight is **2,251,909.54** source units.
- There are **99,441** orders in the order table and **98,666** orders with item rows. AOV among orders with items is **137.75**; median order item value is **86.90**.
- Delivered-account repeat rate is **3.00%** (2,801 of 93,358 accounts with delivered orders had more than one delivered order).
- Average recorded review score is **4.09** across all review rows. Delivered-order reviews average **4.16**.
- Eligible delivered orders average **12.56** days to delivery (median **10.22**); **91.89%** arrived on or before estimate among 96,470 eligible delivered orders.
- The largest customer-state revenue is in **SP**, with **41,375** orders and **5,202,955.05** item revenue.
- The three leading product categories contribute **25.8%** of recorded item revenue: health_beauty (1,258,681.34), watches_gifts (1,205,005.68), bed_bath_table (1,036,988.68).
- Customer-account segments use tie-aware recency and monetary ranks; one-time customers are not split across frequency tiers.

## Interpretation and limitations

The dataset records order and payment activity but does not provide a complete accounting view, product costs, or a basis for calculating profit. Item price and payment value are intentionally reported as separate measures. Late-period sales months have low item-order coverage; use the coverage field and exclude those months from growth interpretation. Customer-level lifetime value is not estimated because the dataset covers a limited historical window and does not establish future behavior.

## Figures

See `visualizations/` for monthly revenue, category/state comparisons, review distribution, delivery-time distribution, and cohort-retention figures.
