"""Evidence-based EDA for the Olist public CSVs used by Marketlytics."""

from __future__ import annotations

import json
import logging
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import seaborn as sns

ROOT = Path(__file__).resolve().parents[2]
RAW = ROOT / "data" / "raw"
REPORTS = ROOT / "reports"
FIGURES = ROOT / "visualizations"
PROCESSED = ROOT / "data" / "processed"


def load_sources() -> dict[str, pd.DataFrame]:
    """Load only the tables/fields needed for the reproducible EDA outputs."""
    files = {
        "orders": "olist_orders_dataset.csv",
        "items": "olist_order_items_dataset.csv",
        "customers": "olist_customers_dataset.csv",
        "products": "olist_products_dataset.csv",
        "categories": "product_category_name_translation.csv",
        "payments": "olist_order_payments_dataset.csv",
        "reviews": "olist_order_reviews_dataset.csv",
    }
    data = {name: pd.read_csv(RAW / filename, dtype=str, keep_default_na=False, encoding="utf-8-sig")
            for name, filename in files.items()}
    for column in ("order_purchase_timestamp", "order_delivered_customer_date", "order_estimated_delivery_date"):
        data["orders"][column] = pd.to_datetime(data["orders"][column], errors="coerce")
    for column in ("price", "freight_value"):
        data["items"][column] = pd.to_numeric(data["items"][column], errors="coerce")
    data["reviews"]["review_score"] = pd.to_numeric(data["reviews"]["review_score"], errors="coerce")
    for column in ("payment_value", "payment_installments"):
        data["payments"][column] = pd.to_numeric(data["payments"][column], errors="coerce")
    data["items"]["order_item_id"] = pd.to_numeric(data["items"]["order_item_id"], errors="coerce")
    return data


def build_analysis_frames(data: dict[str, pd.DataFrame]) -> dict[str, pd.DataFrame]:
    """Create separate order, item, customer, payment, review, and cohort summaries."""
    orders = data["orders"].copy()
    items = data["items"].copy()
    customers = data["customers"].copy()
    order_items = items.groupby("order_id", as_index=False).agg(
        item_revenue=("price", "sum"), freight=("freight_value", "sum"), order_lines=("order_item_id", "count")
    )
    order_geo = (order_items.merge(orders[["order_id", "customer_id", "order_status", "order_purchase_timestamp",
                                                  "order_delivered_customer_date", "order_estimated_delivery_date"]],
                                   on="order_id", validate="one_to_one")
                 .merge(customers[["customer_id", "customer_unique_id", "customer_state"]],
                        on="customer_id", validate="one_to_one"))
    order_geo["month_start"] = order_geo["order_purchase_timestamp"].dt.to_period("M").dt.to_timestamp()
    order_geo["delivery_days"] = (
        order_geo["order_delivered_customer_date"] - order_geo["order_purchase_timestamp"]
    ).dt.total_seconds() / 86400

    order_source_counts = orders.assign(
        month_start=orders["order_purchase_timestamp"].dt.to_period("M").dt.to_timestamp()
    ).groupby("month_start").size().rename("source_order_count")
    item_month = order_geo.groupby("month_start").agg(
        item_revenue=("item_revenue", "sum"), freight=("freight", "sum"),
        orders_with_items=("order_id", "nunique")
    )
    month_index = pd.date_range(orders["order_purchase_timestamp"].min().to_period("M").to_timestamp(),
                                orders["order_purchase_timestamp"].max().to_period("M").to_timestamp(), freq="MS")
    monthly = item_month.reindex(month_index, fill_value=0).rename_axis("month_start").reset_index()
    monthly = monthly.merge(order_source_counts, on="month_start", how="left")
    monthly["source_order_count"] = monthly["source_order_count"].fillna(0).astype(int)
    monthly["item_order_coverage_pct"] = np.where(
        monthly["source_order_count"] > 0,
        100 * monthly["orders_with_items"] / monthly["source_order_count"], np.nan,
    )
    monthly["prior_revenue"] = monthly["item_revenue"].shift(1)
    monthly["prior_orders_with_items"] = monthly["orders_with_items"].shift(1)
    monthly["prior_coverage"] = monthly["item_order_coverage_pct"].shift(1)
    stable_mom = (
        monthly["orders_with_items"].ge(100) & monthly["prior_orders_with_items"].ge(100)
        & monthly["item_order_coverage_pct"].ge(95) & monthly["prior_coverage"].ge(95)
    )
    monthly["mom_revenue_change"] = (monthly["item_revenue"] - monthly["prior_revenue"]).where(stable_mom)
    monthly["mom_revenue_pct"] = (
        100 * monthly["mom_revenue_change"] / monthly["prior_revenue"].replace(0, np.nan)
    ).where(stable_mom)

    category_sales = (items.merge(data["products"][["product_id", "product_category_name"]],
                                  on="product_id", validate="many_to_one")
                      .merge(data["categories"], on="product_category_name", how="left", validate="many_to_one"))
    category_sales["category"] = (category_sales["product_category_name_english"].replace("", np.nan)
                                   .fillna(category_sales["product_category_name"].replace("", np.nan))
                                   .fillna("Unknown"))
    category = category_sales.groupby("category", as_index=False).agg(
        order_lines=("order_id", "size"), orders=("order_id", "nunique"), item_revenue=("price", "sum"),
        freight=("freight_value", "sum"), average_item_price=("price", "mean")
    ).sort_values("item_revenue", ascending=False)

    state = order_geo.groupby("customer_state", as_index=False).agg(
        orders=("order_id", "nunique"), customer_accounts=("customer_unique_id", "nunique"),
        item_revenue=("item_revenue", "sum"), freight=("freight", "sum")
    ).rename(columns={"customer_state": "state"}).sort_values("item_revenue", ascending=False)
    state["aov_per_order"] = state["item_revenue"] / state["orders"]

    customer_orders = (orders.merge(customers[["customer_id", "customer_unique_id", "customer_state"]],
                                    on="customer_id", validate="one_to_one"))
    customer_orders["delivery_days"] = (
        customer_orders["order_delivered_customer_date"] - customer_orders["order_purchase_timestamp"]
    ).dt.total_seconds() / 86400
    delivered_orders = customer_orders[customer_orders["order_status"] == "delivered"].copy()
    eligible_duration = delivered_orders[delivered_orders["delivery_days"].notna() & delivered_orders["delivery_days"].ge(0)].copy()
    delivered_orders["is_on_time"] = (
        delivered_orders["order_delivered_customer_date"] <= delivered_orders["order_estimated_delivery_date"]
    )
    eligible_on_time = delivered_orders[
        delivered_orders["order_delivered_customer_date"].notna()
        & delivered_orders["order_estimated_delivery_date"].notna()
    ].copy()

    delivered_items = order_geo[order_geo["order_status"] == "delivered"].copy()
    rfm_base = (delivered_items.groupby("customer_unique_id", as_index=False)
                .agg(frequency=("order_id", "nunique"), monetary_item_revenue=("item_revenue", "sum"),
                     last_purchase=("order_purchase_timestamp", "max")))
    snapshot = delivered_items["order_purchase_timestamp"].max().normalize() + pd.Timedelta(days=1)
    rfm_base["recency_days"] = (snapshot - rfm_base["last_purchase"].dt.normalize()).dt.days
    n_rfm = len(rfm_base)
    if n_rfm > 1:
        recency_pct = (rfm_base["recency_days"].rank(method="min", ascending=True) - 1) / (n_rfm - 1)
        monetary_pct = (rfm_base["monetary_item_revenue"].rank(method="min", ascending=True) - 1) / (n_rfm - 1)
    else:
        recency_pct = monetary_pct = pd.Series(0, index=rfm_base.index)
    rfm_base["recency_score"] = np.select(
        [recency_pct.le(.2), recency_pct.le(.4), recency_pct.le(.6), recency_pct.le(.8)], [5, 4, 3, 2], default=1
    )
    rfm_base["monetary_score"] = np.select(
        [monetary_pct.ge(.8), monetary_pct.ge(.6), monetary_pct.ge(.4), monetary_pct.ge(.2)], [5, 4, 3, 2], default=1
    )
    rfm_base["frequency_score"] = np.select([rfm_base["frequency"].eq(1), rfm_base["frequency"].eq(2)], [1, 3], default=5)
    rfm_base["rfm_segment"] = np.select(
        [rfm_base["frequency_score"].eq(5) & rfm_base["recency_score"].ge(4) & rfm_base["monetary_score"].ge(4),
         rfm_base["frequency_score"].ge(3),
         rfm_base["frequency_score"].eq(1) & rfm_base["recency_score"].ge(4),
         rfm_base["frequency_score"].eq(1) & rfm_base["recency_score"].le(2)],
        ["Champions", "Repeat customers", "Recent one-time", "Lapsed one-time"], default="Core one-time"
    )
    rfm_summary = rfm_base.groupby("rfm_segment", as_index=False).agg(
        customer_accounts=("customer_unique_id", "size"), average_recency_days=("recency_days", "mean"),
        average_delivered_orders=("frequency", "mean"), average_item_revenue=("monetary_item_revenue", "mean"),
        segment_item_revenue=("monetary_item_revenue", "sum")
    ).sort_values("segment_item_revenue", ascending=False)

    cohort_input = delivered_orders[["customer_unique_id", "order_purchase_timestamp"]].copy()
    cohort_input["activity_month"] = cohort_input["order_purchase_timestamp"].dt.to_period("M").dt.to_timestamp()
    activity = cohort_input[["customer_unique_id", "activity_month"]].drop_duplicates()
    first = activity.groupby("customer_unique_id")["activity_month"].min().rename("cohort_month")
    activity = activity.join(first, on="customer_unique_id")
    activity["months_since_first"] = ((activity["activity_month"].dt.year - activity["cohort_month"].dt.year) * 12
                                       + activity["activity_month"].dt.month - activity["cohort_month"].dt.month)
    cohorts = activity.groupby(["cohort_month", "months_since_first"]).agg(
        active_accounts=("customer_unique_id", "nunique")
    ).reset_index()
    cohort_sizes = activity.groupby("cohort_month")["customer_unique_id"].nunique().rename("cohort_accounts")
    cohorts = cohorts.join(cohort_sizes, on="cohort_month")
    cohorts["retention_pct"] = 100 * cohorts["active_accounts"] / cohorts["cohort_accounts"]

    return {"orders": orders, "items": items, "order_geo": order_geo, "monthly": monthly,
            "category": category, "state": state, "eligible_delivered": delivered_items,
            "eligible_delivery_duration": eligible_duration, "eligible_on_time": eligible_on_time,
            "rfm": rfm_base, "rfm_summary": rfm_summary, "cohorts": cohorts,
            "delivered_all": delivered_orders}


def build_summary(data: dict[str, pd.DataFrame], frames: dict[str, pd.DataFrame]) -> dict:
    """Compute the KPIs and caveats used in the findings report."""
    items = data["items"]
    orders = data["orders"]
    reviews = data["reviews"]
    delivered = frames["delivered_all"]
    customer_accounts = frames["rfm"]["customer_unique_id"].nunique()
    repeat_accounts = int((frames["rfm"]["frequency"] > 1).sum())
    eligible_duration = frames["eligible_delivery_duration"]
    valid_on_time = frames["eligible_on_time"]
    review_by_order = data["reviews"].groupby("order_id")["review_score"].mean()
    delivered_review_scores = orders.loc[orders["order_status"] == "delivered", ["order_id"]].merge(
        review_by_order.rename("average_review_score"), on="order_id", how="inner", validate="one_to_one"
    )["average_review_score"]
    monthly_valid = frames["monthly"].dropna(subset=["mom_revenue_pct"])
    best_growth = None
    if not monthly_valid.empty:
        row = monthly_valid.loc[monthly_valid["mom_revenue_pct"].idxmax()]
        best_growth = {"month": row["month_start"].strftime("%Y-%m"), "pct": float(row["mom_revenue_pct"])}
    total_revenue = float(items["price"].sum())
    category = frames["category"]
    state = frames["state"]
    return {
        "generated_at": pd.Timestamp.now(tz="UTC").isoformat(),
        "currency_note": "Olist item price and freight values are reported as dataset monetary units; confirm currency presentation before publication.",
        "total_orders": int(orders["order_id"].nunique()),
        "orders_with_items": int(items["order_id"].nunique()),
        "total_item_revenue": total_revenue,
        "total_freight": float(items["freight_value"].sum()),
        "aov_orders_with_items": total_revenue / items["order_id"].nunique(),
        "median_order_value": float(items.groupby("order_id")["price"].sum().median()),
        "total_customers_source_rows": int(data["customers"].shape[0]),
        "unique_customer_accounts_source": int(data["customers"]["customer_unique_id"].nunique()),
        "delivered_customer_accounts": int(customer_accounts),
        "repeat_delivered_accounts": repeat_accounts,
        "repeat_delivered_account_rate_pct": 100 * repeat_accounts / customer_accounts,
        "average_review_score_all_records": float(reviews["review_score"].mean()),
        "average_review_score_delivered_orders": float(delivered_review_scores.mean()),
        "delivered_orders": int((orders["order_status"] == "delivered").sum()),
        "eligible_delivery_duration_orders": int(eligible_duration["order_id"].nunique()),
        "average_delivery_days": float(eligible_duration["delivery_days"].mean()),
        "median_delivery_days": float(eligible_duration["delivery_days"].median()),
        "eligible_on_time_orders": int(valid_on_time["order_id"].nunique()),
        "on_time_orders": int(valid_on_time["is_on_time"].sum()),
        "on_time_delivery_pct": 100 * float(valid_on_time["is_on_time"].mean()),
        "top_3_categories": category.head(3)[["category", "item_revenue", "orders"]].to_dict("records"),
        "top_customer_state": state.iloc[0]["state"],
        "top_customer_state_revenue": float(state.iloc[0]["item_revenue"]),
        "top_customer_state_orders": int(state.iloc[0]["orders"]),
        "largest_valid_mom_growth": best_growth,
        "rfm_segments": frames["rfm_summary"].to_dict("records"),
        "payment_values_by_type": data["payments"].groupby("payment_type")["payment_value"].sum().sort_values(ascending=False).to_dict(),
        "scope": "Historical public Olist data; measures are descriptive and do not imply causation or profit.",
    }


def save_figures(data: dict[str, pd.DataFrame], frames: dict[str, pd.DataFrame]) -> None:
    """Save charts answering specific sales, customer, regional, and service questions."""
    FIGURES.mkdir(parents=True, exist_ok=True)
    sns.set_theme(style="whitegrid", palette="deep")

    monthly = frames["monthly"]
    fig, ax = plt.subplots(figsize=(11, 5.5))
    sns.lineplot(data=monthly, x="month_start", y="item_revenue", marker="o", ax=ax, color="#1F6F8B")
    low = monthly[monthly["item_order_coverage_pct"].lt(95) | monthly["orders_with_items"].lt(100)]
    if not low.empty:
        ax.scatter(low["month_start"], low["item_revenue"], color="#D95F02", marker="X", s=70,
                   label="Low item coverage/support")
        ax.legend()
    ax.set(title="Recorded item revenue by purchase month", xlabel="Purchase month", ylabel="Item revenue (source units)")
    ax.tick_params(axis="x", rotation=45)
    fig.tight_layout()
    fig.savefig(FIGURES / "monthly_item_revenue.png", dpi=180)
    plt.close(fig)

    top = frames["category"].head(12).sort_values("item_revenue")
    fig, ax = plt.subplots(figsize=(10, 6))
    sns.barplot(data=top, x="item_revenue", y="category", ax=ax, color="#2A9D8F")
    ax.set(title="Top 12 product categories by item revenue", xlabel="Item revenue (source units)", ylabel="Category")
    fig.tight_layout()
    fig.savefig(FIGURES / "top_categories_revenue.png", dpi=180)
    plt.close(fig)

    top_state = frames["state"].head(10).sort_values("item_revenue")
    fig, ax = plt.subplots(figsize=(8.5, 5.5))
    sns.barplot(data=top_state, x="item_revenue", y="state", ax=ax, color="#457B9D")
    ax.set(title="Top 10 customer states by item revenue", xlabel="Item revenue (source units)", ylabel="Customer state")
    fig.tight_layout()
    fig.savefig(FIGURES / "top_customer_states.png", dpi=180)
    plt.close(fig)

    fig, ax = plt.subplots(figsize=(7, 4.5))
    score_counts = data["reviews"]["review_score"].value_counts().sort_index().rename_axis("review_score").reset_index(name="reviews")
    sns.barplot(data=score_counts, x="review_score", y="reviews", ax=ax, color="#E9C46A")
    ax.set(title="Recorded review-score distribution", xlabel="Review score", ylabel="Review records")
    fig.tight_layout()
    fig.savefig(FIGURES / "review_score_distribution.png", dpi=180)
    plt.close(fig)

    days = frames["eligible_delivered"]["delivery_days"]
    fig, ax = plt.subplots(figsize=(8, 4.8))
    sns.histplot(days, bins=50, kde=True, ax=ax, color="#6A4C93")
    ax.axvline(days.median(), color="#D62828", linestyle="--", label=f"Median: {days.median():.1f} days")
    ax.set(title="Purchase-to-delivery time for delivered orders", xlabel="Days", ylabel="Orders")
    ax.legend()
    fig.tight_layout()
    fig.savefig(FIGURES / "delivery_time_distribution.png", dpi=180)
    plt.close(fig)

    cohort = frames["cohorts"].pivot(index="cohort_month", columns="months_since_first", values="retention_pct")
    cohort = cohort.loc[:, cohort.columns <= 12]
    fig, ax = plt.subplots(figsize=(12, 7))
    sns.heatmap(cohort, cmap="YlGnBu", vmin=0, vmax=100, ax=ax, cbar_kws={"label": "Retained accounts (%)"})
    ax.set(title="Delivered-customer cohort retention", xlabel="Months since first delivered purchase", ylabel="Cohort month")
    fig.tight_layout()
    fig.savefig(FIGURES / "cohort_retention_heatmap.png", dpi=180)
    plt.close(fig)


def write_report(summary: dict, frames: dict[str, pd.DataFrame]) -> None:
    REPORTS.mkdir(parents=True, exist_ok=True)
    PROCESSED.mkdir(parents=True, exist_ok=True)
    (REPORTS / "eda_summary.json").write_text(json.dumps(summary, indent=2, default=str), encoding="utf-8")
    frames["monthly"].to_csv(PROCESSED / "monthly_sales.csv", index=False)
    frames["category"].to_csv(PROCESSED / "category_sales.csv", index=False)
    frames["state"].to_csv(PROCESSED / "customer_state_sales.csv", index=False)
    frames["rfm"].to_csv(PROCESSED / "rfm_customer_segments.csv", index=False)
    frames["rfm_summary"].to_csv(PROCESSED / "rfm_segment_summary.csv", index=False)
    frames["cohorts"].to_csv(PROCESSED / "cohort_retention.csv", index=False)

    top3 = summary["top_3_categories"]
    top_share = 100 * sum(row["item_revenue"] for row in top3) / summary["total_item_revenue"]
    text = [
        "# Marketlytics: evidence-based EDA findings (draft)", "",
        f"Generated: {summary['generated_at']}", "",
        "## Scope and metric definitions", "",
        "- Item revenue is the sum of source order-item `price`; freight is calculated separately.",
        "- AOV divides item revenue by orders with at least one item row (98,666 in this extract).",
        "- Repeat rate and RFM use delivered orders and stable `customer_unique_id`; frequency is based on distinct delivered orders.",
        "- On-time delivery is calculated for delivered orders with both actual and estimated delivery dates.",
        "- MoM figures are emitted only when both months have at least 100 item orders and at least 95% item-order coverage.",
        "- These are descriptive public-data measures; they do not establish causality or profit.", "",
        "## Measured results", "",
        f"- Recorded item revenue is **{summary['total_item_revenue']:,.2f}** source units; freight is **{summary['total_freight']:,.2f}** source units.",
        f"- There are **{summary['total_orders']:,}** orders in the order table and **{summary['orders_with_items']:,}** orders with item rows. AOV among orders with items is **{summary['aov_orders_with_items']:,.2f}**; median order item value is **{summary['median_order_value']:,.2f}**.",
        f"- Delivered-account repeat rate is **{summary['repeat_delivered_account_rate_pct']:.2f}%** ({summary['repeat_delivered_accounts']:,} of {summary['delivered_customer_accounts']:,} accounts with delivered orders had more than one delivered order).",
        f"- Average recorded review score is **{summary['average_review_score_all_records']:.2f}** across all review rows. Delivered-order reviews average **{summary['average_review_score_delivered_orders']:.2f}**.",
        f"- Eligible delivered orders average **{summary['average_delivery_days']:.2f}** days to delivery (median **{summary['median_delivery_days']:.2f}**); **{summary['on_time_delivery_pct']:.2f}%** arrived on or before estimate among {summary['eligible_on_time_orders']:,} eligible delivered orders.",
        f"- The largest customer-state revenue is in **{summary['top_customer_state']}**, with **{summary['top_customer_state_orders']:,}** orders and **{summary['top_customer_state_revenue']:,.2f}** item revenue.",
        f"- The three leading product categories contribute **{top_share:.1f}%** of recorded item revenue: " + ", ".join(f"{row['category']} ({row['item_revenue']:,.2f})" for row in top3) + ".",
        "- Customer-account segments use tie-aware recency and monetary ranks; one-time customers are not split across frequency tiers.",
        "",
        "## Interpretation and limitations", "",
        "The dataset records order and payment activity but does not provide a complete accounting view, product costs, or a basis for calculating profit. Item price and payment value are intentionally reported as separate measures. Late-period sales months have low item-order coverage; use the coverage field and exclude those months from growth interpretation. Customer-level lifetime value is not estimated because the dataset covers a limited historical window and does not establish future behavior.",
        "",
        "## Figures", "",
        "See `visualizations/` for monthly revenue, category/state comparisons, review distribution, delivery-time distribution, and cohort-retention figures.",
        "",
    ]
    (REPORTS / "initial_findings.md").write_text("\n".join(text), encoding="utf-8")


def run_eda() -> dict:
    """Run the complete reproducible EDA and write reports, extracts, and figures."""
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    data = load_sources()
    frames = build_analysis_frames(data)
    summary = build_summary(data, frames)
    save_figures(data, frames)
    write_report(summary, frames)
    logging.info("Wrote EDA report, summary, processed extracts, and six figures.")
    return summary
