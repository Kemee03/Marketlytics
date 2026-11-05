-- Sales uses order-item price as item revenue and reports freight separately.
-- It includes all source order-item rows; it is not recognized accounting revenue.

-- Monthly trend, month-over-month change, and cumulative item revenue. MoM is
-- reported only when both months have at least 100 item orders and 95% item-order
-- coverage. This suppresses sparse first/last months and tiny denominators.
WITH bounds AS (
    SELECT date_trunc('month', min(order_purchase_timestamp))::date AS first_month,
           date_trunc('month', max(order_purchase_timestamp))::date AS last_month
    FROM analytics.fact_orders
), month_spine AS (
    SELECT g.month_start::date AS month_start
    FROM bounds b
    CROSS JOIN LATERAL generate_series(
        b.first_month::timestamp, b.last_month::timestamp, interval '1 month'
    ) AS g(month_start)
), item_sales AS (
    SELECT date_trunc('month', o.order_purchase_timestamp)::date AS month_start,
           sum(i.item_price) AS item_revenue,
           sum(i.freight_value) AS freight,
           count(DISTINCT i.order_id) AS orders_with_items
    FROM analytics.fact_order_items i
    JOIN analytics.fact_orders o USING (order_id)
    GROUP BY 1
), source_orders AS (
    SELECT date_trunc('month', order_purchase_timestamp)::date AS month_start,
           count(*) AS source_order_count
    FROM analytics.fact_orders
    GROUP BY 1
), monthly AS (
    SELECT m.month_start,
           coalesce(s.item_revenue, 0)::numeric AS item_revenue,
           coalesce(s.freight, 0)::numeric AS freight,
           coalesce(s.orders_with_items, 0)::bigint AS orders_with_items,
           coalesce(o.source_order_count, 0)::bigint AS source_order_count
    FROM month_spine m
    LEFT JOIN item_sales s USING (month_start)
    LEFT JOIN source_orders o USING (month_start)
), with_lag AS (
    SELECT *,
           lag(item_revenue) OVER (ORDER BY month_start) AS prior_month_revenue,
           lead(item_revenue) OVER (ORDER BY month_start) AS next_month_revenue,
           lag(source_order_count) OVER (ORDER BY month_start) AS prior_source_order_count,
           lag(orders_with_items) OVER (ORDER BY month_start) AS prior_orders_with_items,
           lag(100.0 * orders_with_items / nullif(source_order_count, 0))
             OVER (ORDER BY month_start) AS prior_item_order_coverage_pct
    FROM monthly
)
SELECT month_start, item_revenue, freight, orders_with_items, source_order_count,
       100.0 * orders_with_items / nullif(source_order_count, 0) AS item_order_coverage_pct,
       item_revenue / nullif(orders_with_items, 0) AS aov_per_order_with_items,
       CASE WHEN orders_with_items >= 100 AND prior_orders_with_items >= 100
                  AND source_order_count > 0 AND prior_source_order_count > 0
                  AND 100.0 * orders_with_items / nullif(source_order_count, 0) >= 95
                  AND prior_item_order_coverage_pct >= 95
            THEN item_revenue - prior_month_revenue END AS mom_revenue_change,
       CASE WHEN orders_with_items >= 100 AND prior_orders_with_items >= 100
                  AND source_order_count > 0 AND prior_source_order_count > 0
                  AND 100.0 * orders_with_items / nullif(source_order_count, 0) >= 95
                  AND prior_item_order_coverage_pct >= 95
            THEN 100.0 * (item_revenue - prior_month_revenue) / nullif(prior_month_revenue, 0)
       END AS mom_revenue_pct,
       next_month_revenue,
       sum(item_revenue) OVER (ORDER BY month_start ROWS UNBOUNDED PRECEDING) AS cumulative_item_revenue
FROM with_lag
ORDER BY month_start;

-- AOV uses orders with item rows as its denominator, not all order statuses.
WITH order_value AS (
    SELECT order_id, sum(item_price) AS item_revenue
    FROM analytics.fact_order_items
    GROUP BY order_id
)
SELECT count(*) AS orders_with_items,
       sum(item_revenue) AS total_item_revenue,
       avg(item_revenue) AS average_order_value,
       percentile_cont(0.5) WITHIN GROUP (ORDER BY item_revenue) AS median_order_value
FROM order_value;

-- Quarterly revenue rollup.
SELECT date_trunc('quarter', o.order_purchase_timestamp)::date AS quarter_start,
       sum(i.item_price) AS item_revenue,
       sum(i.freight_value) AS freight,
       count(DISTINCT i.order_id) AS orders_with_items
FROM analytics.fact_order_items i
JOIN analytics.fact_orders o USING (order_id)
GROUP BY 1
ORDER BY 1;

-- Revenue and demand by category. Untranslated/null categories remain visible.
SELECT coalesce(p.product_category_name_english, p.product_category_name, 'Unknown') AS category,
       count(*) AS order_lines,
       count(DISTINCT i.order_id) AS orders,
       sum(i.item_price) AS item_revenue,
       sum(i.freight_value) AS freight,
       avg(i.item_price) AS average_item_price
FROM analytics.fact_order_items i
JOIN analytics.dim_products p USING (product_id)
GROUP BY 1
HAVING sum(i.item_price) > 0
ORDER BY item_revenue DESC;
