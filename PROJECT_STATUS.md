# Marketlytics project status

Updated: 2026-11-05

## Phase checklist

- [x] Phase 1 — Repository structure, raw dataset checks, and PostgreSQL staging setup.
- [x] Phase 2 — Profile, clean, and model source data.
- [x] Phase 3 — Advanced SQL analytical queries and metric integrity checks.
- [x] Phase 4 — Python exploratory analysis and customer/cohort analysis.
- [x] Phase 5 — Statistical visualizations with reproducible figures.
- [x] Phase 6 — Excel business reporting.
- [x] Phase 7 — Tableau dashboards published to Tableau Public.
- [x] Phase 8 — Evidence-based insights, tests, documentation, and portfolio polish.

## Phase 1 evidence and blockers

- Repository scaffold and project documentation created.
- Source manifest includes all nine expected Olist CSV names and required headers.
- Data preflight checks file presence, duplicate/missing headers, required headers, parseability, and row counts; it never fabricates missing files.
- User-provided archive is extracted in `data/raw/`; all nine files passed preflight (including 99,441 orders, 112,650 order items, and 1,000,163 geolocation rows).
- PostgreSQL staging tables preserve source columns as `TEXT`; all nine CSVs loaded in one committed transaction.
- Phase 2 profile generated at `reports/data_quality_profile.md` and `.json`: declared keys and six source foreign-key checks pass; no numeric or datetime parse failures were observed.
- Geography coverage is incomplete: 278 customer rows and 42 seller rows have no ZIP-prefix/state geolocation match. The model preserves those records with null coordinates.
- `review_id` repeats 814 times as a standalone key; (`review_id`, `order_id`) is unique and is the planned review fact key.
- Star-schema grain, key, fan-out, and null-handling decisions are documented in `database/er_diagram/star_schema.md`.
- Typed model in `database/analytics_model.sql` is applied. The seven source-to-model row counts match; item/payment/review measures passed checks, and no delivered-before-purchase timestamps were found.
- Seven topic-based analytical SQL files cover inventory, sales, customer/RFM, products, geography, operations, and cohorts; outputs use order-grain rollups to prevent fan-out.
- `scripts/run_analytics_sql.ps1` runs the seven analytical SQL files in order and stops on the first SQL error.
- All seven analytical SQL files ran successfully. The trend query includes missing calendar months and suppresses MoM changes unless both months have at least 100 item orders and 95% item-order coverage; RFM scores keep ties together and orient higher recency scores toward recent purchases; review averages are limited to delivered orders.
- Initial measured metrics from SQL: $13,591,643.70 item revenue, $137.75 AOV across 98,666 orders with items, 91.89% on-time delivery among eligible delivered orders, and a 3.00% repeat delivered-account rate.
- Raw data and `.env` are excluded from Git.
- Three automated preflight unit tests pass; Python sources compile successfully.
- Git repository initialized; no commit created.
- **Dataset status:** all nine user-provided Olist CSVs are present and validated in `data/raw/`.
- **Database status:** Docker PostgreSQL 18.6 container `marketlytics-postgres` is healthy on localhost port 5434; `staging` and `analytics` schemas were created, Python dependencies installed, and staging load committed.

## Decisions

- Use the current folder as repository root because it was empty at inspection.
- Keep staging values as text; defer typed conversion to documented transformation logic after inspecting actual source data.
- Publish numerical findings only after their definitions and edge-month coverage checks are validated against the source.
## Phase 4–6 evidence (2026-11-05)

- Python EDA ran successfully and generated six figures in `visualizations/`: monthly item revenue, category revenue, customer-state revenue, review scores, delivery time, and cohort retention.
- Reproducible processed extracts are in `data/processed/`; headline definitions and measured results are in `reports/initial_findings.md` and `reports/eda_summary.json`.
- EDA headline metrics: item revenue 13,591,643.70 source units; freight 2,251,909.54; AOV 137.75 across 98,666 orders with items; repeat delivered-account rate 3.00%; on-time delivery 91.89% among 96,470 eligible delivered orders; mean delivery 12.56 days.
- Excel business report exported to `excel/Marketlytics_Business_Report.xlsx` with executive summary, monthly sales, category/state detail, RFM segments, cohort retention, metric definitions, and a native monthly revenue chart.
- Three Python unit tests pass; EDA modules compile. Workbook exported and visually reviewed; no Excel desktop recalculation check was available.
- Tableau Public workbook **Marketlytics Sales and Customer Retention** published with Executive Performance and Customer Retention dashboards: https://public.tableau.com/app/profile/kemee.kemee/viz/MarketlyticsSalesandCustomerRetention/CustomerRetention
- The user confirmed that both published dashboards render correctly. The Tableau link is recorded in `README.md`; tests, documentation, and final visual review are complete.



