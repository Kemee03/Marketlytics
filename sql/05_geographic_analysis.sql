-- Customer-state view attributes order value to the state on that order's
-- customer_id record; repeated customer_unique_id values are counted distinctly.
WITH item_by_order AS (
    SELECT order_id, sum(item_price) AS item_revenue, sum(freight_value) AS freight
    FROM analytics.fact_order_items GROUP BY order_id
)
SELECT c.state,
       count(DISTINCT o.order_id) AS orders,
       count(DISTINCT c.customer_unique_id) AS customer_accounts,
       sum(i.item_revenue) AS item_revenue,
       sum(i.freight) AS freight,
       sum(i.item_revenue) / nullif(count(DISTINCT o.order_id), 0) AS aov_per_order
FROM analytics.fact_orders o
JOIN analytics.dim_customers c USING (customer_id)
JOIN item_by_order i USING (order_id)
GROUP BY c.state
ORDER BY item_revenue DESC;

-- Seller-state category of fulfillment, based on item lines and price.
SELECT s.state,
       count(*) AS order_lines,
       count(DISTINCT i.order_id) AS orders,
       count(DISTINCT i.seller_id) AS sellers,
       sum(i.item_price) AS item_revenue,
       sum(i.freight_value) AS freight
FROM analytics.fact_order_items i
JOIN analytics.dim_sellers s USING (seller_id)
GROUP BY s.state
ORDER BY item_revenue DESC;

-- Geolocation coverage after enrichment. Null coordinates are kept and measurable.
SELECT has_geolocation_match,
       count(*) AS zip_state_pairs,
       sum(geolocation_observation_count) AS source_coordinate_observations
FROM analytics.dim_geography
GROUP BY has_geolocation_match
ORDER BY has_geolocation_match DESC;
