-- Phase 3: source/model inventory and basic integrity checks.
-- Run after database/analytics_model.sql.

-- 1. Source-aligned counts versus typed model counts.
SELECT 'orders' AS entity, (SELECT count(*) FROM staging.orders) AS staging_rows,
       (SELECT count(*) FROM analytics.fact_orders) AS model_rows
UNION ALL SELECT 'order_items', (SELECT count(*) FROM staging.order_items), (SELECT count(*) FROM analytics.fact_order_items)
UNION ALL SELECT 'payments', (SELECT count(*) FROM staging.order_payments), (SELECT count(*) FROM analytics.fact_payments)
UNION ALL SELECT 'reviews', (SELECT count(*) FROM staging.order_reviews), (SELECT count(*) FROM analytics.fact_reviews)
UNION ALL SELECT 'customers', (SELECT count(*) FROM staging.customers), (SELECT count(*) FROM analytics.dim_customers)
UNION ALL SELECT 'products', (SELECT count(*) FROM staging.products), (SELECT count(*) FROM analytics.dim_products)
UNION ALL SELECT 'sellers', (SELECT count(*) FROM staging.sellers), (SELECT count(*) FROM analytics.dim_sellers)
ORDER BY entity;

-- 2. Order status distribution.
SELECT order_status, count(*) AS orders,
       round(100.0 * count(*) / sum(count(*)) OVER (), 2) AS pct_of_orders
FROM analytics.fact_orders
GROUP BY order_status
ORDER BY orders DESC;

-- 3. Grain checks. Expect no duplicates for these declared keys.
SELECT 'orders.order_id' AS key_name, count(*) AS duplicate_key_count
FROM (SELECT order_id FROM analytics.fact_orders GROUP BY order_id HAVING count(*) > 1) d
UNION ALL
SELECT 'order_items.order_id + order_item_id', count(*)
FROM (SELECT order_id, order_item_id FROM analytics.fact_order_items GROUP BY order_id, order_item_id HAVING count(*) > 1) d
UNION ALL
SELECT 'payments.order_id + payment_sequential', count(*)
FROM (SELECT order_id, payment_sequential FROM analytics.fact_payments GROUP BY order_id, payment_sequential HAVING count(*) > 1) d
UNION ALL
SELECT 'reviews.review_id + order_id', count(*)
FROM (SELECT review_id, order_id FROM analytics.fact_reviews GROUP BY review_id, order_id HAVING count(*) > 1) d;

-- 4. Example of safe aggregation at order grain before combining measures.
WITH item_order AS (
    SELECT order_id, sum(item_price) AS item_revenue
    FROM analytics.fact_order_items GROUP BY order_id
), payment_order AS (
    SELECT order_id, sum(payment_value) AS payment_value
    FROM analytics.fact_payments GROUP BY order_id
)
SELECT count(*) AS comparable_orders,
       sum(item_revenue) AS item_revenue,
       sum(payment_value) AS recorded_payment_value,
       sum(payment_value - item_revenue) AS payment_minus_item_value
FROM item_order i
JOIN payment_order p USING (order_id);
-- Payment minus item value is a reconciliation difference, not profit.
