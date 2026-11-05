-- Delivery performance only uses delivered orders with both delivery timestamps.
SELECT count(*) FILTER (WHERE order_status = 'delivered') AS delivered_orders,
       count(delivery_duration_days) AS eligible_duration_orders,
       avg(delivery_duration_days) AS average_delivery_days,
       percentile_cont(0.5) WITHIN GROUP (ORDER BY delivery_duration_days) AS median_delivery_days,
       count(*) FILTER (WHERE is_on_time IS NOT NULL) AS eligible_on_time_orders,
       count(*) FILTER (WHERE is_on_time) AS on_time_orders,
       100.0 * count(*) FILTER (WHERE is_on_time)
           / nullif(count(*) FILTER (WHERE is_on_time IS NOT NULL), 0) AS on_time_delivery_pct
FROM analytics.fact_orders;

-- Monthly delivery and review comparison. Association is descriptive, not causal.
WITH order_review AS (
    SELECT order_id, avg(review_score) AS average_review_score
    FROM analytics.fact_reviews GROUP BY order_id
)
SELECT date_trunc('month', o.order_purchase_timestamp)::date AS purchase_month,
       count(*) FILTER (WHERE o.order_status = 'delivered') AS delivered_orders,
       avg(o.delivery_duration_days) AS average_delivery_days,
       avg(r.average_review_score) FILTER (WHERE o.order_status = 'delivered') AS delivered_order_average_review_score,
       corr(o.delivery_duration_days::double precision,
            r.average_review_score::double precision)
            FILTER (WHERE o.order_status = 'delivered') AS delivery_days_review_score_correlation
FROM analytics.fact_orders o
LEFT JOIN order_review r USING (order_id)
GROUP BY 1
ORDER BY 1;

-- Payment behavior remains at payment-sequence grain.
SELECT payment_type,
       count(*) AS payment_records,
       count(DISTINCT order_id) AS orders,
       sum(payment_value) AS payment_value,
       avg(payment_installments) AS average_installments
FROM analytics.fact_payments
GROUP BY payment_type
ORDER BY payment_value DESC;
