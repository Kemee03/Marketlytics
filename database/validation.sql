-- Run after database/analytics_model.sql.
-- The row-count comparison should match for each source-to-fact/dimension pair.
SELECT 'customers -> dim_customers' AS comparison,
       (SELECT count(*) FROM staging.customers) AS staging_rows,
       (SELECT count(*) FROM analytics.dim_customers) AS analytics_rows
UNION ALL
SELECT 'orders -> fact_orders',
       (SELECT count(*) FROM staging.orders),
       (SELECT count(*) FROM analytics.fact_orders)
UNION ALL
SELECT 'order_items -> fact_order_items',
       (SELECT count(*) FROM staging.order_items),
       (SELECT count(*) FROM analytics.fact_order_items)
UNION ALL
SELECT 'payments -> fact_payments',
       (SELECT count(*) FROM staging.order_payments),
       (SELECT count(*) FROM analytics.fact_payments)
UNION ALL
SELECT 'reviews -> fact_reviews',
       (SELECT count(*) FROM staging.order_reviews),
       (SELECT count(*) FROM analytics.fact_reviews)
UNION ALL
SELECT 'products -> dim_products',
       (SELECT count(*) FROM staging.products),
       (SELECT count(*) FROM analytics.dim_products)
UNION ALL
SELECT 'sellers -> dim_sellers',
       (SELECT count(*) FROM staging.sellers),
       (SELECT count(*) FROM analytics.dim_sellers)
ORDER BY comparison;

-- Null/negative checks for measures and date logic. Every result should be zero,
-- except the out-of-time-order delivery count, which is reported for inspection.
SELECT
    (SELECT count(*) FROM analytics.fact_order_items
      WHERE item_price IS NULL OR freight_value IS NULL OR item_price < 0 OR freight_value < 0) AS invalid_item_measures,
    (SELECT count(*) FROM analytics.fact_payments WHERE payment_value IS NULL) AS missing_payment_values,
    (SELECT count(*) FROM analytics.fact_reviews WHERE review_score NOT BETWEEN 1 AND 5) AS invalid_review_scores,
    (SELECT count(*) FROM analytics.fact_orders
      WHERE order_delivered_customer_date < order_purchase_timestamp) AS delivered_before_purchase;

-- This deliberately keeps item, payment, and review metrics at separate grains.
-- Compare these independently; never join the three raw facts and sum their values.
WITH item_by_order AS (
    SELECT order_id, sum(item_price) AS item_revenue, sum(freight_value) AS freight
    FROM analytics.fact_order_items
    GROUP BY order_id
), payment_by_order AS (
    SELECT order_id, sum(payment_value) AS payment_value
    FROM analytics.fact_payments
    GROUP BY order_id
), review_by_order AS (
    SELECT order_id, count(*) AS review_count, avg(review_score) AS average_review_score
    FROM analytics.fact_reviews
    GROUP BY order_id
)
SELECT
    (SELECT count(*) FROM analytics.fact_orders) AS order_count,
    (SELECT count(*) FROM item_by_order) AS orders_with_items,
    (SELECT count(*) FROM payment_by_order) AS orders_with_payments,
    (SELECT count(*) FROM review_by_order) AS orders_with_reviews,
    (SELECT sum(item_revenue) FROM item_by_order) AS total_item_revenue,
    (SELECT sum(freight) FROM item_by_order) AS total_freight,
    (SELECT sum(payment_value) FROM payment_by_order) AS total_payment_value;
