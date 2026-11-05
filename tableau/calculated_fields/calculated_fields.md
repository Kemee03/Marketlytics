# Tableau Calculated Fields

Create these fields on the matching source only.

## Monthly Sales

**Item Revenue**: `SUM([item_revenue])`

**Freight**: `SUM([freight])`

**AOV**: `SUM([item_revenue]) / SUM([orders_with_items])`

**MoM Revenue Change %**: use the supplied `mom_revenue_pct` field. Keep nulls null; do not replace with zero.

**Coverage Warning**: `IF ISNULL([item_order_coverage_pct]) OR [item_order_coverage_pct] < 95 THEN "Low / unavailable coverage" ELSE "Coverage adequate" END`

## Customer Segments

**Segment Accounts**: `SUM([customer_accounts])`

**Segment Item Revenue**: `SUM([segment_item_revenue])`

## Cohort Retention

**Retention %**: `[retention_pct] / 100`

Format as Percentage. Source values are percentage points (for example, 100 means 100%).

## Customer State

**State Item Revenue**: `SUM([item_revenue])`

Use distinct extract tables per dashboard section. Do not relate or physically join these pre-aggregated files to each other.
