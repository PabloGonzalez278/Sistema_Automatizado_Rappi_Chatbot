"""
Data Loader Module - Carga y procesa datos operacionales de Rappi desde Excel.
"""
import pandas as pd
import numpy as np
from pathlib import Path

DATA_PATH = Path(__file__).parent.parent / "data" / "rappi_data.xlsx"

WEEK_LABELS = ["L8W", "L7W", "L6W", "L5W", "L4W", "L3W", "L2W", "L1W", "L0W"]
WEEK_LABELS_ROLL = [f"{w}_ROLL" for w in WEEK_LABELS]


def load_metrics() -> pd.DataFrame:
    df = pd.read_excel(DATA_PATH, sheet_name="RAW_INPUT_METRICS")
    week_cols = [c for c in df.columns if c.endswith("_ROLL")]
    df_melted = df.melt(
        id_vars=["COUNTRY", "CITY", "ZONE", "ZONE_TYPE", "ZONE_PRIORITIZATION", "METRIC"],
        value_vars=week_cols,
        var_name="WEEK",
        value_name="VALUE",
    )
    df_melted["WEEK"] = df_melted["WEEK"].str.replace("_ROLL", "")
    df_melted["WEEK_NUM"] = df_melted["WEEK"].map({w: i for i, w in enumerate(WEEK_LABELS)})
    return df_melted


def load_orders() -> pd.DataFrame:
    df = pd.read_excel(DATA_PATH, sheet_name="RAW_ORDERS")
    week_cols = [c for c in df.columns if c.startswith("L") and c.endswith("W")]
    df_melted = df.melt(
        id_vars=["COUNTRY", "CITY", "ZONE", "METRIC"],
        value_vars=week_cols,
        var_name="WEEK",
        value_name="VALUE",
    )
    df_melted["WEEK_NUM"] = df_melted["WEEK"].map({w: i for i, w in enumerate(WEEK_LABELS)})
    return df_melted


def load_metrics_wide() -> pd.DataFrame:
    return pd.read_excel(DATA_PATH, sheet_name="RAW_INPUT_METRICS")


def load_orders_wide() -> pd.DataFrame:
    return pd.read_excel(DATA_PATH, sheet_name="RAW_ORDERS")


def get_data_summary() -> dict:
    metrics_df = load_metrics_wide()
    orders_df = load_orders_wide()
    return {
        "countries": sorted(metrics_df["COUNTRY"].unique().tolist()),
        "cities": sorted(metrics_df["CITY"].unique().tolist()),
        "metrics": sorted(metrics_df["METRIC"].unique().tolist()),
        "zone_types": sorted(metrics_df["ZONE_TYPE"].unique().tolist()),
        "zone_prioritizations": sorted(metrics_df["ZONE_PRIORITIZATION"].unique().tolist()),
        "total_zones_metrics": len(metrics_df),
        "total_zones_orders": len(orders_df),
        "weeks": WEEK_LABELS,
        "orders_cities": sorted(orders_df["CITY"].unique().tolist()),
    }


def query_data(
    dataset: str = "metrics",
    countries: list[str] | None = None,
    cities: list[str] | None = None,
    zones: list[str] | None = None,
    metrics: list[str] | None = None,
    zone_types: list[str] | None = None,
    zone_prioritizations: list[str] | None = None,
) -> pd.DataFrame:
    if dataset == "orders":
        df = load_orders_wide()
    else:
        df = load_metrics_wide()

    if countries:
        df = df[df["COUNTRY"].isin(countries)]
    if cities:
        df = df[df["CITY"].isin(cities)]
    if zones:
        df = df[df["ZONE"].isin(zones)]
    if metrics:
        df = df[df["METRIC"].isin(metrics)]
    if zone_types and "ZONE_TYPE" in df.columns:
        df = df[df["ZONE_TYPE"].isin(zone_types)]
    if zone_prioritizations and "ZONE_PRIORITIZATION" in df.columns:
        df = df[df["ZONE_PRIORITIZATION"].isin(zone_prioritizations)]

    return df


def compute_trends(df: pd.DataFrame, week_cols: list[str]) -> pd.DataFrame:
    """Compute week-over-week changes and trends."""
    result = df.copy()
    values = result[week_cols].values
    if values.shape[1] >= 2:
        last = values[:, -1]
        prev = values[:, -2]
        with np.errstate(divide="ignore", invalid="ignore"):
            result["WOW_CHANGE"] = last - prev
            result["WOW_PCT_CHANGE"] = np.where(prev != 0, (last - prev) / np.abs(prev) * 100, 0)

        first = values[:, 0]
        with np.errstate(divide="ignore", invalid="ignore"):
            result["TOTAL_CHANGE"] = last - first
            result["TOTAL_PCT_CHANGE"] = np.where(first != 0, (last - first) / np.abs(first) * 100, 0)

        slopes = []
        x = np.arange(values.shape[1])
        for row in values:
            valid = ~np.isnan(row)
            if valid.sum() >= 2:
                slope = np.polyfit(x[valid], row[valid], 1)[0]
                slopes.append(slope)
            else:
                slopes.append(0)
        result["TREND_SLOPE"] = slopes
    return result


def get_context_for_llm() -> str:
    """Generate a comprehensive data context string for the LLM."""
    summary = get_data_summary()
    metrics_df = load_metrics_wide()
    orders_df = load_orders_wide()

    week_cols_metrics = [c for c in metrics_df.columns if c.endswith("_ROLL")]
    week_cols_orders = [c for c in orders_df.columns if c.startswith("L") and c.endswith("W")]

    metric_stats = []
    for metric in summary["metrics"]:
        mdf = metrics_df[metrics_df["METRIC"] == metric]
        latest = mdf[week_cols_metrics[-1]]
        prev = mdf[week_cols_metrics[-2]]
        metric_stats.append(
            f"  - {metric}: avg={latest.mean():.4f}, median={latest.median():.4f}, "
            f"min={latest.min():.4f}, max={latest.max():.4f}, "
            f"WoW avg change={( latest.mean() - prev.mean()):.4f}"
        )

    orders_latest = orders_df[["CITY", "ZONE", week_cols_orders[-1]]].copy()
    orders_latest.columns = ["CITY", "ZONE", "ORDERS"]
    top_cities = orders_latest.groupby("CITY")["ORDERS"].sum().sort_values(ascending=False).head(10)

    country_orders = orders_df.groupby("COUNTRY")[week_cols_orders[-1]].sum().sort_values(ascending=False)

    context = f"""=== RAPPI OPERATIONAL DATA CONTEXT ===

DATASETS AVAILABLE:
1. RAW_INPUT_METRICS: {len(metrics_df)} rows - Operational metrics by country/city/zone over 9 weeks (L8W oldest to L0W most recent)
2. RAW_ORDERS: {len(orders_df)} rows - Order counts by country/city/zone over 9 weeks

DIMENSIONS:
- Countries ({len(summary['countries'])}): {', '.join(summary['countries'])}
- Cities: {len(summary['cities'])} total
- Zone Types: {', '.join(summary['zone_types'])}
- Zone Prioritizations: {', '.join(summary['zone_prioritizations'])}
- Time: 9 rolling weeks (L8W=oldest, L0W=most recent/current week)

METRICS ({len(summary['metrics'])}):
{chr(10).join(metric_stats)}

TOP 10 CITIES BY ORDERS (L0W):
{chr(10).join(f'  - {city}: {orders:,.0f}' for city, orders in top_cities.items())}

ORDERS BY COUNTRY (L0W):
{chr(10).join(f'  - {country}: {orders:,.0f}' for country, orders in country_orders.items())}

METRIC DESCRIPTIONS:
- Perfect Orders: % of orders completed without issues (higher=better)
- % Order Loss: % of orders lost/cancelled (lower=better)
- Gross Profit UE: Unit economics gross profit per order
- Pro Adoption: % of users with Rappi Pro subscription
- Turbo Adoption: % of orders using Rappi Turbo (fast delivery)
- Lead Penetration: % conversion from leads
- Restaurants SST > SS CVR: Restaurant search-to-store conversion rate
- Retail SST > SS CVR: Retail search-to-store conversion rate
- Restaurants SS > ATC CVR: Restaurant store-to-add-to-cart conversion rate
- Restaurants Markdowns / GMV: Discount ratio in restaurants
- % Restaurants Sessions With Optimal Assortment: Restaurant menu completeness
- MLTV Top Verticals Adoption: Multi-vertical lifetime value adoption
- Non-Pro PTC > OP: Non-Pro purchase-to-order placement conversion
- % PRO Users Who Breakeven: % of Pro users whose savings offset subscription cost

WEEK INTERPRETATION:
- L0W = current/most recent week
- L1W = last week (1 week ago)
- LNW = N weeks ago
- L8W = oldest available (8 weeks ago)
"""
    return context
