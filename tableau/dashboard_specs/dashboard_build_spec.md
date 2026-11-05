# Marketlytics Tableau Dashboard Build Spec

## Data source files

Connect to the five CSVs in `tableau/data_sources/`. Each file is pre-aggregated at its stated grain; use the matching source for each view. Do not join these extracts together because their grains differ.

| Source | Grain | Main use |
|---|---|---|
| `marketlytics_monthly_sales.csv` | One row per calendar month | Revenue trend and coverage-aware growth |
| `marketlytics_category_sales.csv` | One row per product category | Category performance |
| `marketlytics_customer_state_sales.csv` | One row per customer state | Geographic ranking |
| `marketlytics_customer_segments.csv` | One row per RFM segment | Customer-value mix |
| `marketlytics_cohort_retention.csv` | One row per cohort and month since first order | Retention heatmap |

## Dashboard 1 — Executive Performance

Audience: business stakeholders. Canvas: 1200 × 800, white background, dark navy titles, restrained teal accent.

- KPI tiles: item revenue, item freight, orders with items, AOV, repeat delivered-account rate, on-time delivery rate.
- Main line: monthly item revenue from `monthly_sales`; label the y-axis `Source units` until currency is confirmed.
- Category horizontal bars: item revenue, descending; show top 10, with an optional category filter.
- State horizontal bars or filled map: item revenue by state; SP should rank first. Prefer bars if the state field is not recognized as geographic.
- Add a note: revenue is not profit, delivery rate uses only eligible delivered orders, and late-period sales have low item-order coverage.

## Dashboard 2 — Customer Retention

- KPI: delivered-account repeat rate (3.00%).
- RFM segment table/bar: accounts, average recency days, delivered orders/account, and item revenue/account.
- Cohort heatmap: rows = `cohort_month`, columns = `months_since_first`, color = `retention_pct`; display as percentage points. Filter to cohorts with sufficient follow-up when comparing later months.
- Explain that repeat behavior is observed within this historical dataset window and is not a forecast of lifetime value.

## Dashboard 3 — Sales Quality & Operations (optional)

If rebuilding from the full SQL model, include on-time delivery and review metrics. Keep the delivered-order population and eligibility denominator visible. Do not blend review, payment, order-item, and order facts before aggregating to a common grain.

## Formatting and QA

- Use `month_start` as a date, sorted ascending.
- Do not interpret blank `mom_revenue_pct` as 0%; it is intentionally suppressed when prior/current months fail coverage or support requirements.
- Verify revenue sum equals 13,591,643.70 source units; monthly order sum equals 98,666; customer-state SP revenue equals 5,202,955.05.
- Confirm all filters affect intended views only and expose the data-period boundary (2016–2018).
- Save the Tableau workbook as `tableau/Marketlytics_Dashboards.twbx` only after all dashboard views pass a visual check.
