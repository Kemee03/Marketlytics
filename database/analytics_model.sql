-- Rebuild the typed Marketlytics analytics star schema from text-preserving staging.
-- This script replaces analytics tables only; raw files and staging tables remain intact.
BEGIN;

CREATE SCHEMA IF NOT EXISTS analytics;

DROP TABLE IF EXISTS analytics.fact_reviews, analytics.fact_payments,
    analytics.fact_order_items, analytics.fact_orders CASCADE;
DROP TABLE IF EXISTS analytics.dim_date, analytics.dim_geography,
    analytics.dim_sellers, analytics.dim_products, analytics.dim_customers CASCADE;

CREATE TABLE analytics.dim_date (
    date_key integer PRIMARY KEY,
    calendar_date date NOT NULL UNIQUE,
    calendar_year smallint NOT NULL,
    calendar_quarter smallint NOT NULL,
    calendar_month smallint NOT NULL,
    month_start date NOT NULL,
    day_of_month smallint NOT NULL,
    iso_day_of_week smallint NOT NULL,
    day_name text NOT NULL
);

INSERT INTO analytics.dim_date
SELECT to_char(d::date, 'YYYYMMDD')::integer,
       d::date,
       extract(year FROM d)::smallint,
       extract(quarter FROM d)::smallint,
       extract(month FROM d)::smallint,
       date_trunc('month', d)::date,
       extract(day FROM d)::smallint,
       extract(isodow FROM d)::smallint,
       trim(to_char(d, 'Day'))
FROM generate_series(
    (SELECT min(NULLIF(trim(order_purchase_timestamp), '')::date) FROM staging.orders),
    (SELECT max(NULLIF(trim(order_estimated_delivery_date), '')::date) FROM staging.orders),
    interval '1 day'
) AS d;

-- Grain: normalized postal prefix plus state. Include customer/seller location pairs
-- even when the source geolocation table has no matching coordinate observations.
CREATE TABLE analytics.dim_geography (
    zip_prefix text NOT NULL,
    state text NOT NULL,
    city text,
    latitude numeric(10, 6),
    longitude numeric(10, 6),
    geolocation_observation_count integer NOT NULL DEFAULT 0,
    has_geolocation_match boolean NOT NULL,
    PRIMARY KEY (zip_prefix, state)
);

WITH geo_observations AS (
    SELECT lpad(trim(geolocation_zip_code_prefix), 5, '0') AS zip_prefix,
           upper(trim(geolocation_state)) AS state,
           NULLIF(trim(geolocation_city), '') AS city,
           NULLIF(trim(geolocation_lat), '')::numeric AS latitude,
           NULLIF(trim(geolocation_lng), '')::numeric AS longitude
    FROM staging.geolocation
), geo_aggregated AS (
    SELECT zip_prefix, state,
           mode() WITHIN GROUP (ORDER BY city) FILTER (WHERE city IS NOT NULL) AS city,
           avg(latitude)::numeric(10, 6) AS latitude,
           avg(longitude)::numeric(10, 6) AS longitude,
           count(*)::integer AS observation_count
    FROM geo_observations
    GROUP BY zip_prefix, state
), source_locations AS (
    SELECT lpad(trim(customer_zip_code_prefix), 5, '0') AS zip_prefix,
           upper(trim(customer_state)) AS state,
           NULLIF(trim(customer_city), '') AS city
    FROM staging.customers
    UNION ALL
    SELECT lpad(trim(seller_zip_code_prefix), 5, '0'),
           upper(trim(seller_state)),
           NULLIF(trim(seller_city), '')
    FROM staging.sellers
), source_location_names AS (
    SELECT zip_prefix, state,
           mode() WITHIN GROUP (ORDER BY city) FILTER (WHERE city IS NOT NULL) AS city
    FROM source_locations
    GROUP BY zip_prefix, state
), all_location_keys AS (
    SELECT zip_prefix, state FROM geo_aggregated
    UNION
    SELECT zip_prefix, state FROM source_location_names
)
INSERT INTO analytics.dim_geography
    (zip_prefix, state, city, latitude, longitude, geolocation_observation_count, has_geolocation_match)
SELECT keys.zip_prefix, keys.state,
       coalesce(geo.city, source.city), geo.latitude, geo.longitude,
       coalesce(geo.observation_count, 0), geo.zip_prefix IS NOT NULL
FROM all_location_keys AS keys
LEFT JOIN geo_aggregated AS geo USING (zip_prefix, state)
LEFT JOIN source_location_names AS source USING (zip_prefix, state);

-- Grain: one Olist customer_id (order-context identity). customer_unique_id is the
-- stable repeat-purchase account identifier and is intentionally non-unique here.
CREATE TABLE analytics.dim_customers AS
SELECT trim(customer_id) AS customer_id,
       trim(customer_unique_id) AS customer_unique_id,
       lpad(trim(customer_zip_code_prefix), 5, '0') AS zip_prefix,
       upper(trim(customer_state)) AS state,
       trim(customer_city) AS city
FROM staging.customers;
ALTER TABLE analytics.dim_customers ADD PRIMARY KEY (customer_id);
ALTER TABLE analytics.dim_customers ALTER COLUMN customer_unique_id SET NOT NULL;
ALTER TABLE analytics.dim_customers
    ADD CONSTRAINT fk_dim_customers_geography
    FOREIGN KEY (zip_prefix, state) REFERENCES analytics.dim_geography (zip_prefix, state);

CREATE TABLE analytics.dim_products AS
SELECT trim(p.product_id) AS product_id,
       NULLIF(trim(p.product_category_name), '') AS product_category_name,
       t.product_category_name_english,
       NULLIF(trim(p.product_name_lenght), '')::integer AS product_name_length,
       NULLIF(trim(p.product_description_lenght), '')::integer AS product_description_length,
       NULLIF(trim(p.product_photos_qty), '')::integer AS product_photos_qty,
       NULLIF(trim(p.product_weight_g), '')::numeric AS product_weight_g,
       NULLIF(trim(p.product_length_cm), '')::numeric AS product_length_cm,
       NULLIF(trim(p.product_height_cm), '')::numeric AS product_height_cm,
       NULLIF(trim(p.product_width_cm), '')::numeric AS product_width_cm
FROM staging.products AS p
LEFT JOIN staging.product_category_translation AS t
  ON NULLIF(trim(p.product_category_name), '') = trim(t.product_category_name);
ALTER TABLE analytics.dim_products ADD PRIMARY KEY (product_id);

CREATE TABLE analytics.dim_sellers AS
SELECT trim(seller_id) AS seller_id,
       lpad(trim(seller_zip_code_prefix), 5, '0') AS zip_prefix,
       upper(trim(seller_state)) AS state,
       trim(seller_city) AS city
FROM staging.sellers;
ALTER TABLE analytics.dim_sellers ADD PRIMARY KEY (seller_id);
ALTER TABLE analytics.dim_sellers
    ADD CONSTRAINT fk_dim_sellers_geography
    FOREIGN KEY (zip_prefix, state) REFERENCES analytics.dim_geography (zip_prefix, state);

CREATE TABLE analytics.fact_orders (
    order_id text PRIMARY KEY,
    customer_id text NOT NULL REFERENCES analytics.dim_customers (customer_id),
    order_status text NOT NULL,
    purchase_date_key integer NOT NULL REFERENCES analytics.dim_date (date_key),
    approval_date_key integer REFERENCES analytics.dim_date (date_key),
    carrier_date_key integer REFERENCES analytics.dim_date (date_key),
    delivered_date_key integer REFERENCES analytics.dim_date (date_key),
    estimated_delivery_date_key integer REFERENCES analytics.dim_date (date_key),
    order_purchase_timestamp timestamp NOT NULL,
    order_approved_at timestamp,
    order_delivered_carrier_date timestamp,
    order_delivered_customer_date timestamp,
    order_estimated_delivery_date timestamp,
    delivery_duration_days numeric(12, 4),
    is_on_time boolean
);

INSERT INTO analytics.fact_orders
SELECT trim(order_id), trim(customer_id), trim(order_status),
       to_char(purchase_ts::date, 'YYYYMMDD')::integer,
       to_char(approval_ts::date, 'YYYYMMDD')::integer,
       to_char(carrier_ts::date, 'YYYYMMDD')::integer,
       to_char(delivered_ts::date, 'YYYYMMDD')::integer,
       to_char(estimated_ts::date, 'YYYYMMDD')::integer,
       purchase_ts, approval_ts, carrier_ts, delivered_ts, estimated_ts,
       CASE WHEN trim(order_status) = 'delivered' AND delivered_ts IS NOT NULL
                  AND delivered_ts >= purchase_ts
            THEN extract(epoch FROM (delivered_ts - purchase_ts)) / 86400 END,
       CASE WHEN trim(order_status) = 'delivered' AND delivered_ts IS NOT NULL
                  AND estimated_ts IS NOT NULL
            THEN delivered_ts <= estimated_ts END
FROM (
    SELECT *,
           NULLIF(trim(order_purchase_timestamp), '')::timestamp AS purchase_ts,
           NULLIF(trim(order_approved_at), '')::timestamp AS approval_ts,
           NULLIF(trim(order_delivered_carrier_date), '')::timestamp AS carrier_ts,
           NULLIF(trim(order_delivered_customer_date), '')::timestamp AS delivered_ts,
           NULLIF(trim(order_estimated_delivery_date), '')::timestamp AS estimated_ts
    FROM staging.orders
) AS parsed;

-- Grain: one product/seller line per order. Revenue and freight remain separate measures.
CREATE TABLE analytics.fact_order_items AS
SELECT trim(order_id) AS order_id,
       NULLIF(trim(order_item_id), '')::integer AS order_item_id,
       trim(product_id) AS product_id,
       trim(seller_id) AS seller_id,
       NULLIF(trim(shipping_limit_date), '')::timestamp AS shipping_limit_date,
       NULLIF(trim(price), '')::numeric(12, 2) AS item_price,
       NULLIF(trim(freight_value), '')::numeric(12, 2) AS freight_value
FROM staging.order_items;
ALTER TABLE analytics.fact_order_items
    ADD PRIMARY KEY (order_id, order_item_id),
    ADD CONSTRAINT fk_fact_order_items_order FOREIGN KEY (order_id) REFERENCES analytics.fact_orders (order_id),
    ADD CONSTRAINT fk_fact_order_items_product FOREIGN KEY (product_id) REFERENCES analytics.dim_products (product_id),
    ADD CONSTRAINT fk_fact_order_items_seller FOREIGN KEY (seller_id) REFERENCES analytics.dim_sellers (seller_id);
ALTER TABLE analytics.fact_order_items
    ALTER COLUMN product_id SET NOT NULL,
    ALTER COLUMN seller_id SET NOT NULL,
    ALTER COLUMN item_price SET NOT NULL,
    ALTER COLUMN freight_value SET NOT NULL,
    ADD CONSTRAINT ck_fact_order_items_nonnegative CHECK (item_price >= 0 AND freight_value >= 0);

-- Grain: one payment sequence per order. Aggregate this fact by order before joining to order lines.
CREATE TABLE analytics.fact_payments AS
SELECT trim(order_id) AS order_id,
       NULLIF(trim(payment_sequential), '')::integer AS payment_sequential,
       trim(payment_type) AS payment_type,
       NULLIF(trim(payment_installments), '')::integer AS payment_installments,
       NULLIF(trim(payment_value), '')::numeric(12, 2) AS payment_value
FROM staging.order_payments;
ALTER TABLE analytics.fact_payments
    ALTER COLUMN payment_type SET NOT NULL,
    ALTER COLUMN payment_value SET NOT NULL,
    ADD PRIMARY KEY (order_id, payment_sequential),
    ADD CONSTRAINT fk_fact_payments_order FOREIGN KEY (order_id) REFERENCES analytics.fact_orders (order_id);

-- review_id repeats across orders; the pair is the profiled unique key.
CREATE TABLE analytics.fact_reviews AS
SELECT trim(review_id) AS review_id,
       trim(order_id) AS order_id,
       NULLIF(trim(review_score), '')::smallint AS review_score,
       NULLIF(trim(review_comment_title), '') AS review_comment_title,
       NULLIF(trim(review_comment_message), '') AS review_comment_message,
       NULLIF(trim(review_creation_date), '')::timestamp AS review_creation_date,
       NULLIF(trim(review_answer_timestamp), '')::timestamp AS review_answer_timestamp
FROM staging.order_reviews;
ALTER TABLE analytics.fact_reviews
    ADD PRIMARY KEY (review_id, order_id),
    ADD CONSTRAINT fk_fact_reviews_order FOREIGN KEY (order_id) REFERENCES analytics.fact_orders (order_id);
ALTER TABLE analytics.fact_reviews
    ALTER COLUMN review_score SET NOT NULL,
    ADD CONSTRAINT ck_fact_reviews_score CHECK (review_score BETWEEN 1 AND 5);

CREATE INDEX ix_fact_orders_customer ON analytics.fact_orders (customer_id);
CREATE INDEX ix_dim_customers_unique_id ON analytics.dim_customers (customer_unique_id);
CREATE INDEX ix_fact_order_items_product ON analytics.fact_order_items (product_id);
CREATE INDEX ix_fact_order_items_seller ON analytics.fact_order_items (seller_id);
CREATE INDEX ix_fact_payments_order ON analytics.fact_payments (order_id);
CREATE INDEX ix_fact_reviews_order ON analytics.fact_reviews (order_id);

COMMENT ON TABLE analytics.fact_order_items IS 'One order line. SUM(item_price) is item revenue; freight_value is reported separately.';
COMMENT ON TABLE analytics.fact_payments IS 'One payment sequence. Aggregate by order before combining with order-item metrics.';
COMMENT ON TABLE analytics.fact_reviews IS 'One review_id/order_id pair; review_id is not unique by itself in the source.';
COMMENT ON TABLE analytics.dim_geography IS 'One normalized ZIP-prefix/state pair; entity locations without source coordinates are retained with null latitude/longitude.';

COMMIT;
