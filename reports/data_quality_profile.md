# Olist data quality profile

Generated: 2026-11-05T08:09:29.665853+00:00

This report was computed from the nine user-supplied source CSVs. Blank strings are counted as missing; source records are not modified.

## Source inventory

| File | Rows | Columns | Blank cells | Declared-key duplicate rows | Declared-key missing rows |
|---|---:|---:|---:|---:|---:|
| `olist_customers_dataset.csv` | 99,441 | 5 | 0 | 0 | 0 |
| `olist_geolocation_dataset.csv` | 1,000,163 | 5 | 0 | — | — |
| `olist_order_items_dataset.csv` | 112,650 | 7 | 0 | 0 | 0 |
| `olist_order_payments_dataset.csv` | 103,886 | 5 | 0 | 0 | 0 |
| `olist_order_reviews_dataset.csv` | 99,224 | 7 | 145,903 | 0 | 0 |
| `olist_orders_dataset.csv` | 99,441 | 8 | 4,908 | 0 | 0 |
| `olist_products_dataset.csv` | 32,951 | 9 | 2,448 | 0 | 0 |
| `olist_sellers_dataset.csv` | 3,095 | 4 | 0 | 0 | 0 |
| `product_category_name_translation.csv` | 71 | 2 | 0 | 0 | 0 |

## Missingness by field

Only fields with blanks are listed. Missingness in delivery timestamps and review text is preserved for later rule-based treatment.

### `olist_order_reviews_dataset.csv`

| Field | Blank rows | Share of file |
|---|---:|---:|
| `review_comment_title` | 87,656 | 88.3% |
| `review_comment_message` | 58,247 | 58.7% |

### `olist_orders_dataset.csv`

| Field | Blank rows | Share of file |
|---|---:|---:|
| `order_delivered_customer_date` | 2,965 | 3.0% |
| `order_delivered_carrier_date` | 1,783 | 1.8% |
| `order_approved_at` | 160 | 0.2% |

### `olist_products_dataset.csv`

| Field | Blank rows | Share of file |
|---|---:|---:|
| `product_category_name` | 610 | 1.9% |
| `product_description_lenght` | 610 | 1.9% |
| `product_name_lenght` | 610 | 1.9% |
| `product_photos_qty` | 610 | 1.9% |
| `product_height_cm` | 2 | 0.0% |
| `product_length_cm` | 2 | 0.0% |
| `product_weight_g` | 2 | 0.0% |
| `product_width_cm` | 2 | 0.0% |

## Referential integrity

| Child relation | Parent relation | Nonblank child values | Blank child values | Unmatched values |
|---|---|---:|---:|---:|
| `olist_orders_dataset.csv:customer_id` | `olist_customers_dataset.csv:customer_id` | 99,441 | 0 | 0 |
| `olist_order_items_dataset.csv:order_id` | `olist_orders_dataset.csv:order_id` | 112,650 | 0 | 0 |
| `olist_order_items_dataset.csv:product_id` | `olist_products_dataset.csv:product_id` | 112,650 | 0 | 0 |
| `olist_order_items_dataset.csv:seller_id` | `olist_sellers_dataset.csv:seller_id` | 112,650 | 0 | 0 |
| `olist_order_payments_dataset.csv:order_id` | `olist_orders_dataset.csv:order_id` | 103,886 | 0 | 0 |
| `olist_order_reviews_dataset.csv:order_id` | `olist_orders_dataset.csv:order_id` | 99,224 | 0 | 0 |

## Geography lookup coverage

Geography is matched on normalized ZIP prefix plus state because some ZIP prefixes occur in more than one state.

| Source | Source rows | Distinct ZIP/state pairs | Rows without a geolocation match | Unmatched distinct pairs |
|---|---:|---:|---:|---:|
| `olist_customers_dataset.csv` | 99,441 | 14,994 | 278 | 157 |
| `olist_sellers_dataset.csv` | 3,095 | 2,264 | 42 | 41 |

## Type parsing checks

Numeric and datetime fields were parsed for quality assessment only; raw staging remains text-preserving.

No nonblank numeric or datetime parse failures were observed in the profiled fields.

## Modeling implications

- `order_items` grain is one order line (`order_id`, `order_item_id`); item revenue and freight belong at this grain.
- `order_payments` grain is one payment sequence per order; aggregate to order before joining to order-line revenue.
- `order_reviews` is a separate order-review grain; do not join raw payments, items, and reviews together before aggregation.
- Geolocation has no supplied unique row identifier. Model it as a ZIP-prefix lookup after profiling/choosing an explicit aggregation rule.
- Customer and seller locations do not all match the geolocation file. Model a documented unknown/missing geography record instead of dropping those entities or forcing a false match.
- Blank values are retained in staging. A blank delivery timestamp can mean an order was not delivered; it must not be imputed as zero days.
- Revenue is the sum of item `price`; freight is reported separately. These public records do not support a profit calculation.

## Limitations

This is a source-quality profile, not a statistical business findings report. It does not assert that a source field is correct merely because it parses. Business metrics and recommendations are deferred until transformations and metric definitions are validated.
