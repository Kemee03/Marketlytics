-- Product metrics use order-item grain. Ranking is dense so ties share a rank.
WITH product_sales AS (
    SELECT p.product_id,
           coalesce(p.product_category_name_english, p.product_category_name, 'Unknown') AS category,
           count(*) AS order_lines,
           count(DISTINCT i.order_id) AS orders,
           sum(i.item_price) AS item_revenue,
           avg(i.item_price) AS average_item_price,
           percentile_cont(0.5) WITHIN GROUP (ORDER BY i.item_price) AS median_item_price
    FROM analytics.fact_order_items i
    JOIN analytics.dim_products p USING (product_id)
    GROUP BY p.product_id, category
)
SELECT *,
       rank() OVER (ORDER BY item_revenue DESC) AS revenue_rank,
       dense_rank() OVER (ORDER BY item_revenue DESC) AS dense_revenue_rank,
       row_number() OVER (ORDER BY item_revenue DESC, product_id) AS deterministic_row_number
FROM product_sales
ORDER BY revenue_rank, product_id
LIMIT 20;

-- Category demand and revenue; avoids joining payment/review facts.
SELECT coalesce(p.product_category_name_english, p.product_category_name, 'Unknown') AS category,
       count(*) AS order_lines,
       count(DISTINCT i.order_id) AS orders,
       sum(i.item_price) AS item_revenue,
       avg(i.item_price) AS average_item_price,
       percentile_cont(0.5) WITHIN GROUP (ORDER BY i.item_price) AS median_item_price
FROM analytics.fact_order_items i
JOIN analytics.dim_products p USING (product_id)
GROUP BY 1
ORDER BY item_revenue DESC;
