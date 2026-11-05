-- Customer identity uses customer_unique_id; source customer_id is order-context.

-- Repeat-purchase behavior. Orders here are delivered orders with item records.
WITH item_by_order AS (
    SELECT order_id, sum(item_price) AS item_revenue
    FROM analytics.fact_order_items GROUP BY order_id
), delivered AS (
    SELECT o.order_id, c.customer_unique_id, o.order_purchase_timestamp, i.item_revenue
    FROM analytics.fact_orders o
    JOIN analytics.dim_customers c USING (customer_id)
    JOIN item_by_order i USING (order_id)
    WHERE o.order_status = 'delivered'
), customer_orders AS (
    SELECT customer_unique_id,
           count(DISTINCT order_id) AS delivered_orders,
           sum(item_revenue) AS delivered_item_revenue,
           max(order_purchase_timestamp) AS last_purchase
    FROM delivered
    GROUP BY customer_unique_id
)
SELECT count(*) AS delivered_customer_accounts,
       count(*) FILTER (WHERE delivered_orders > 1) AS repeat_accounts,
       100.0 * count(*) FILTER (WHERE delivered_orders > 1) / nullif(count(*), 0) AS repeat_account_rate_pct,
       avg(delivered_orders) AS delivered_orders_per_account,
       avg(delivered_item_revenue) AS average_delivered_item_revenue_per_account
FROM customer_orders;

-- RFM scores based on delivered orders. Snapshot is one day after the latest
-- delivered purchase. Recency score 5 means most recent; tied values share a score.
WITH item_by_order AS (
    SELECT order_id, sum(item_price) AS item_revenue
    FROM analytics.fact_order_items GROUP BY order_id
), delivered AS (
    SELECT o.order_id, c.customer_unique_id, o.order_purchase_timestamp, i.item_revenue
    FROM analytics.fact_orders o
    JOIN analytics.dim_customers c USING (customer_id)
    JOIN item_by_order i USING (order_id)
    WHERE o.order_status = 'delivered'
), snapshot AS (
    SELECT max(order_purchase_timestamp)::date + 1 AS snapshot_date FROM delivered
), rfm AS (
    SELECT customer_unique_id,
           (SELECT snapshot_date FROM snapshot) - max(order_purchase_timestamp)::date AS recency_days,
           count(DISTINCT order_id) AS frequency,
           sum(item_revenue) AS monetary_item_revenue
    FROM delivered
    GROUP BY customer_unique_id
), scored AS (
    SELECT *,
           CASE
             WHEN percent_rank() OVER (ORDER BY recency_days ASC) <= 0.2 THEN 5
             WHEN percent_rank() OVER (ORDER BY recency_days ASC) <= 0.4 THEN 4
             WHEN percent_rank() OVER (ORDER BY recency_days ASC) <= 0.6 THEN 3
             WHEN percent_rank() OVER (ORDER BY recency_days ASC) <= 0.8 THEN 2
             ELSE 1
           END AS recency_score,
           CASE WHEN frequency = 1 THEN 1 WHEN frequency = 2 THEN 3 ELSE 5 END AS frequency_score,
           CASE
             WHEN percent_rank() OVER (ORDER BY monetary_item_revenue) >= 0.8 THEN 5
             WHEN percent_rank() OVER (ORDER BY monetary_item_revenue) >= 0.6 THEN 4
             WHEN percent_rank() OVER (ORDER BY monetary_item_revenue) >= 0.4 THEN 3
             WHEN percent_rank() OVER (ORDER BY monetary_item_revenue) >= 0.2 THEN 2
             ELSE 1
           END AS monetary_score
    FROM rfm
), segmented AS (
    SELECT *,
       CASE
         WHEN frequency_score = 5 AND recency_score >= 4 AND monetary_score >= 4 THEN 'Champions'
         WHEN frequency_score >= 3 THEN 'Repeat customers'
         WHEN frequency_score = 1 AND recency_score >= 4 THEN 'Recent one-time'
         WHEN frequency_score = 1 AND recency_score <= 2 THEN 'Lapsed one-time'
         ELSE 'Core one-time'
       END AS rfm_segment
    FROM scored
)
SELECT rfm_segment,
       count(*) AS customer_accounts,
       avg(recency_days) AS average_recency_days,
       avg(frequency) AS average_delivered_orders,
       avg(monetary_item_revenue) AS average_item_revenue,
       sum(monetary_item_revenue) AS segment_item_revenue
FROM segmented
GROUP BY rfm_segment
ORDER BY segment_item_revenue DESC;

-- New versus returning by purchase month (delivered orders only).
WITH accounts AS (
    SELECT c.customer_unique_id,
           date_trunc('month', o.order_purchase_timestamp)::date AS month_start,
           min(date_trunc('month', o.order_purchase_timestamp)::date)
             OVER (PARTITION BY c.customer_unique_id) AS first_purchase_month
    FROM analytics.fact_orders o
    JOIN analytics.dim_customers c USING (customer_id)
    WHERE o.order_status = 'delivered'
), monthly AS (
    SELECT month_start,
           count(DISTINCT customer_unique_id) FILTER (WHERE month_start = first_purchase_month) AS new_accounts,
           count(DISTINCT customer_unique_id) FILTER (WHERE month_start > first_purchase_month) AS returning_accounts
    FROM accounts GROUP BY month_start
)
SELECT *, new_accounts + returning_accounts AS purchasing_accounts
FROM monthly ORDER BY month_start;
