-- Monthly retention cohorts use stable customer_unique_id and delivered orders.
-- Retention is the share of cohort accounts purchasing again in each cohort month.
WITH account_month AS (
    SELECT DISTINCT c.customer_unique_id,
           date_trunc('month', o.order_purchase_timestamp)::date AS activity_month
    FROM analytics.fact_orders o
    JOIN analytics.dim_customers c USING (customer_id)
    WHERE o.order_status = 'delivered'
), first_activity AS (
    SELECT customer_unique_id, min(activity_month) AS cohort_month
    FROM account_month
    GROUP BY customer_unique_id
), cohort_size AS (
    SELECT cohort_month, count(*) AS cohort_accounts
    FROM first_activity
    GROUP BY cohort_month
), cohort_activity AS (
    SELECT f.cohort_month, a.activity_month,
           ((extract(year FROM a.activity_month) - extract(year FROM f.cohort_month)) * 12
             + extract(month FROM a.activity_month) - extract(month FROM f.cohort_month))::integer AS months_since_first,
           count(DISTINCT a.customer_unique_id) AS active_accounts
    FROM first_activity f
    JOIN account_month a USING (customer_unique_id)
    GROUP BY f.cohort_month, a.activity_month
)
SELECT a.cohort_month, a.activity_month, a.months_since_first,
       s.cohort_accounts, a.active_accounts,
       100.0 * a.active_accounts / nullif(s.cohort_accounts, 0) AS retention_pct
FROM cohort_activity a
JOIN cohort_size s USING (cohort_month)
ORDER BY a.cohort_month, a.months_since_first;

-- Compact cohort matrix suitable for a heatmap/export.
WITH account_month AS (
    SELECT DISTINCT c.customer_unique_id,
           date_trunc('month', o.order_purchase_timestamp)::date AS activity_month
    FROM analytics.fact_orders o
    JOIN analytics.dim_customers c USING (customer_id)
    WHERE o.order_status = 'delivered'
), first_activity AS (
    SELECT customer_unique_id, min(activity_month) AS cohort_month
    FROM account_month GROUP BY customer_unique_id
), cohort_size AS (
    SELECT cohort_month, count(*) AS cohort_accounts
    FROM first_activity GROUP BY cohort_month
), monthly_retention AS (
    SELECT f.cohort_month,
           ((extract(year FROM a.activity_month) - extract(year FROM f.cohort_month)) * 12
             + extract(month FROM a.activity_month) - extract(month FROM f.cohort_month))::integer AS months_since_first,
           100.0 * count(DISTINCT a.customer_unique_id) / nullif(max(s.cohort_accounts), 0) AS retention_pct
    FROM first_activity f
    JOIN account_month a USING (customer_unique_id)
    JOIN cohort_size s USING (cohort_month)
    GROUP BY f.cohort_month, a.activity_month
)
SELECT cohort_month,
       max(retention_pct) FILTER (WHERE months_since_first = 0) AS month_0,
       max(retention_pct) FILTER (WHERE months_since_first = 1) AS month_1,
       max(retention_pct) FILTER (WHERE months_since_first = 2) AS month_2,
       max(retention_pct) FILTER (WHERE months_since_first = 3) AS month_3,
       max(retention_pct) FILTER (WHERE months_since_first = 6) AS month_6,
       max(retention_pct) FILTER (WHERE months_since_first = 12) AS month_12
FROM monthly_retention
GROUP BY cohort_month
ORDER BY cohort_month;
