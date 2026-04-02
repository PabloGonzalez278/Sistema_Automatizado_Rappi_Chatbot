"""
Insights Engine - Genera insights automaticos y reportes ejecutivos a partir de datos operacionales de Rappi.
"""
import anthropic
import pandas as pd
import numpy as np
from datetime import datetime
from data_loader import (
    load_metrics_wide, load_orders_wide, compute_trends,
    get_data_summary, WEEK_LABELS,
)


class InsightsEngine:
    def __init__(self, api_key: str):
        self.client = anthropic.Anthropic(api_key=api_key)
        self.metrics_df = load_metrics_wide()
        self.orders_df = load_orders_wide()
        self.summary = get_data_summary()

    def generate_full_report(self) -> dict:
        """Generate the complete executive report with all insight categories."""
        anomalies = self._detect_anomalies()
        trends = self._detect_trends()
        benchmarking = self._perform_benchmarking()
        correlations = self._find_correlations()
        opportunities = self._find_opportunities()

        raw_insights = {
            "anomalies": anomalies,
            "concerning_trends": trends,
            "benchmarking": benchmarking,
            "correlations": correlations,
            "opportunities": opportunities,
        }

        report_md = self._generate_executive_report(raw_insights)

        return {
            "report_markdown": report_md,
            "raw_insights": raw_insights,
            "generated_at": datetime.now().isoformat(),
        }

    def _detect_anomalies(self) -> list[dict]:
        """Detect statistical anomalies in the data."""
        anomalies = []
        week_cols = [c for c in self.metrics_df.columns if c.endswith("_ROLL")]
        latest = week_cols[-1]
        prev = week_cols[-2]

        for metric in self.metrics_df["METRIC"].unique():
            mdf = self.metrics_df[self.metrics_df["METRIC"] == metric].copy()
            vals_latest = mdf[latest]
            vals_prev = mdf[prev]

            mean = vals_latest.mean()
            std = vals_latest.std()

            if std == 0:
                continue

            mdf["z_score"] = (vals_latest - mean) / std
            outliers = mdf[mdf["z_score"].abs() > 2]

            for _, row in outliers.iterrows():
                wow_change = row[latest] - row[prev]
                anomalies.append({
                    "type": "statistical_outlier",
                    "metric": metric,
                    "country": row["COUNTRY"],
                    "city": row["CITY"],
                    "zone": row["ZONE"],
                    "value": round(row[latest], 4),
                    "mean": round(mean, 4),
                    "z_score": round(row["z_score"], 2),
                    "wow_change": round(wow_change, 4),
                    "severity": "high" if abs(row["z_score"]) > 3 else "medium",
                    "direction": "above" if row["z_score"] > 0 else "below",
                })

            changes = vals_latest - vals_prev
            change_mean = changes.mean()
            change_std = changes.std()
            if change_std > 0:
                mdf["change_z"] = (changes - change_mean) / change_std
                spikes = mdf[mdf["change_z"].abs() > 2.5]
                for _, row in spikes.iterrows():
                    if row.name not in outliers.index:
                        anomalies.append({
                            "type": "sudden_change",
                            "metric": metric,
                            "country": row["COUNTRY"],
                            "city": row["CITY"],
                            "zone": row["ZONE"],
                            "value": round(row[latest], 4),
                            "prev_value": round(row[prev], 4),
                            "change": round(row[latest] - row[prev], 4),
                            "severity": "high" if abs(row["change_z"]) > 3 else "medium",
                        })

        anomalies.sort(key=lambda x: 0 if x["severity"] == "high" else 1)
        return anomalies[:30]

    def _detect_trends(self) -> list[dict]:
        """Detect concerning trends over the 9-week period."""
        trends = []
        week_cols = [c for c in self.metrics_df.columns if c.endswith("_ROLL")]

        negative_metrics = ["% Order Loss", "Restaurants Markdowns / GMV"]

        for metric in self.metrics_df["METRIC"].unique():
            is_negative = metric in negative_metrics

            for group_col in ["COUNTRY", "CITY"]:
                grouped = self.metrics_df[self.metrics_df["METRIC"] == metric].groupby(group_col)
                for name, group in grouped:
                    weekly_avgs = [group[w].mean() for w in week_cols]
                    x = np.arange(len(weekly_avgs))
                    valid = ~np.isnan(weekly_avgs)
                    if sum(valid) < 4:
                        continue

                    slope = np.polyfit(x[valid], np.array(weekly_avgs)[valid], 1)[0]
                    total_change = weekly_avgs[-1] - weekly_avgs[0]
                    pct_change = (total_change / abs(weekly_avgs[0]) * 100) if weekly_avgs[0] != 0 else 0

                    consecutive_bad = 0
                    for i in range(1, len(weekly_avgs)):
                        if is_negative:
                            if weekly_avgs[i] > weekly_avgs[i - 1]:
                                consecutive_bad += 1
                            else:
                                consecutive_bad = 0
                        else:
                            if weekly_avgs[i] < weekly_avgs[i - 1]:
                                consecutive_bad += 1
                            else:
                                consecutive_bad = 0

                    is_concerning = False
                    if is_negative and slope > 0.005:
                        is_concerning = True
                    elif not is_negative and slope < -0.005:
                        is_concerning = True
                    elif consecutive_bad >= 3:
                        is_concerning = True

                    if is_concerning:
                        trends.append({
                            "metric": metric,
                            "group_by": group_col,
                            "group_value": name,
                            "slope": round(slope, 6),
                            "total_change_pct": round(pct_change, 2),
                            "consecutive_deterioration_weeks": consecutive_bad,
                            "weekly_values": [round(v, 4) for v in weekly_avgs],
                            "severity": "high" if (abs(pct_change) > 10 or consecutive_bad >= 5) else "medium",
                        })

        trends.sort(key=lambda x: abs(x["total_change_pct"]), reverse=True)
        return trends[:25]

    def _perform_benchmarking(self) -> list[dict]:
        """Benchmark performance across countries, zones, and prioritizations."""
        benchmarks = []
        week_cols = [c for c in self.metrics_df.columns if c.endswith("_ROLL")]
        latest = week_cols[-1]

        for metric in self.metrics_df["METRIC"].unique():
            mdf = self.metrics_df[self.metrics_df["METRIC"] == metric]
            country_avgs = mdf.groupby("COUNTRY")[latest].mean().sort_values(ascending=False)

            if len(country_avgs) >= 2:
                best = country_avgs.index[0]
                worst = country_avgs.index[-1]
                gap = country_avgs.iloc[0] - country_avgs.iloc[-1]
                overall_avg = country_avgs.mean()

                benchmarks.append({
                    "type": "country_benchmark",
                    "metric": metric,
                    "best_performer": best,
                    "best_value": round(country_avgs.iloc[0], 4),
                    "worst_performer": worst,
                    "worst_value": round(country_avgs.iloc[-1], 4),
                    "gap": round(gap, 4),
                    "overall_avg": round(overall_avg, 4),
                    "all_values": {k: round(v, 4) for k, v in country_avgs.items()},
                })

        for metric in self.metrics_df["METRIC"].unique():
            mdf = self.metrics_df[self.metrics_df["METRIC"] == metric]
            zone_avgs = mdf.groupby("ZONE_TYPE")[latest].mean()
            if len(zone_avgs) == 2:
                wealthy = zone_avgs.get("Wealthy", 0)
                non_wealthy = zone_avgs.get("Non Wealthy", 0)
                benchmarks.append({
                    "type": "zone_type_benchmark",
                    "metric": metric,
                    "wealthy_avg": round(wealthy, 4),
                    "non_wealthy_avg": round(non_wealthy, 4),
                    "gap": round(wealthy - non_wealthy, 4),
                    "gap_pct": round((wealthy - non_wealthy) / abs(non_wealthy) * 100, 2) if non_wealthy != 0 else 0,
                })

        for metric in self.metrics_df["METRIC"].unique():
            mdf = self.metrics_df[self.metrics_df["METRIC"] == metric]
            prio_avgs = mdf.groupby("ZONE_PRIORITIZATION")[latest].mean()
            if len(prio_avgs) >= 2:
                benchmarks.append({
                    "type": "prioritization_benchmark",
                    "metric": metric,
                    "values": {k: round(v, 4) for k, v in prio_avgs.items()},
                })

        return benchmarks

    def _find_correlations(self) -> list[dict]:
        """Find meaningful correlations between metrics."""
        correlations = []
        week_cols = [c for c in self.metrics_df.columns if c.endswith("_ROLL")]
        latest = week_cols[-1]

        pivot = self.metrics_df.pivot_table(
            index=["COUNTRY", "CITY", "ZONE"],
            columns="METRIC",
            values=latest,
            aggfunc="mean"
        ).dropna(axis=1, how="all")

        if len(pivot.columns) >= 2:
            corr = pivot.corr()
            for i in range(len(corr.columns)):
                for j in range(i + 1, len(corr.columns)):
                    val = corr.iloc[i, j]
                    if not np.isnan(val) and abs(val) > 0.3:
                        correlations.append({
                            "metric_1": corr.columns[i],
                            "metric_2": corr.columns[j],
                            "correlation": round(val, 3),
                            "strength": "strong" if abs(val) > 0.7 else ("moderate" if abs(val) > 0.5 else "weak"),
                            "direction": "positive" if val > 0 else "negative",
                        })

        orders_by_zone = self.orders_df.groupby(["COUNTRY", "CITY", "ZONE"])[
            [c for c in self.orders_df.columns if c.startswith("L") and c.endswith("W")][-1]
        ].mean()

        if not orders_by_zone.empty:
            merged = pivot.join(orders_by_zone.rename("ORDERS"), how="inner")
            if "ORDERS" in merged.columns and len(merged) > 10:
                for col in pivot.columns:
                    if col in merged.columns:
                        valid = merged[[col, "ORDERS"]].dropna()
                        if len(valid) > 10:
                            r = valid[col].corr(valid["ORDERS"])
                            if not np.isnan(r) and abs(r) > 0.2:
                                correlations.append({
                                    "metric_1": col,
                                    "metric_2": "Order Volume",
                                    "correlation": round(r, 3),
                                    "strength": "strong" if abs(r) > 0.7 else ("moderate" if abs(r) > 0.5 else "weak"),
                                    "direction": "positive" if r > 0 else "negative",
                                })

        correlations.sort(key=lambda x: abs(x["correlation"]), reverse=True)
        return correlations[:20]

    def _find_opportunities(self) -> list[dict]:
        """Identify actionable opportunities."""
        opportunities = []
        week_cols = [c for c in self.metrics_df.columns if c.endswith("_ROLL")]
        latest = week_cols[-1]

        prio_zones = self.metrics_df[self.metrics_df["ZONE_PRIORITIZATION"].isin(["High Priority", "Prioritized"])]
        non_prio = self.metrics_df[self.metrics_df["ZONE_PRIORITIZATION"] == "Not Prioritized"]

        for metric in self.metrics_df["METRIC"].unique():
            prio_metric = prio_zones[prio_zones["METRIC"] == metric]
            non_prio_metric = non_prio[non_prio["METRIC"] == metric]

            if len(prio_metric) > 0 and len(non_prio_metric) > 0:
                non_prio_avg = non_prio_metric[latest].mean()
                underperformers = prio_metric[prio_metric[latest] < non_prio_avg]
                if len(underperformers) > 0:
                    for _, row in underperformers.head(5).iterrows():
                        opportunities.append({
                            "type": "underperforming_priority_zone",
                            "metric": metric,
                            "country": row["COUNTRY"],
                            "city": row["CITY"],
                            "zone": row["ZONE"],
                            "value": round(row[latest], 4),
                            "benchmark": round(non_prio_avg, 4),
                            "gap": round(row[latest] - non_prio_avg, 4),
                            "priority": "high",
                        })

        df_trends = compute_trends(self.metrics_df, week_cols)
        improving = df_trends[df_trends["WOW_PCT_CHANGE"] > 5].sort_values("WOW_PCT_CHANGE", ascending=False)
        for _, row in improving.head(10).iterrows():
            opportunities.append({
                "type": "momentum_opportunity",
                "metric": row["METRIC"],
                "country": row["COUNTRY"],
                "city": row["CITY"],
                "zone": row["ZONE"],
                "wow_improvement": round(row["WOW_PCT_CHANGE"], 2),
                "current_value": round(row[latest], 4),
                "priority": "medium",
            })

        adoption_metrics = ["Pro Adoption (Last Week Status)", "Turbo Adoption", "MLTV Top Verticals Adoption"]
        for metric in adoption_metrics:
            mdf = self.metrics_df[self.metrics_df["METRIC"] == metric]
            if len(mdf) > 0:
                overall_avg = mdf[latest].mean()
                low_adoption = mdf[mdf[latest] < overall_avg * 0.5]
                for _, row in low_adoption.head(5).iterrows():
                    opportunities.append({
                        "type": "adoption_gap",
                        "metric": metric,
                        "country": row["COUNTRY"],
                        "city": row["CITY"],
                        "zone": row["ZONE"],
                        "current_adoption": round(row[latest], 4),
                        "average_adoption": round(overall_avg, 4),
                        "gap_pct": round((1 - row[latest] / overall_avg) * 100, 1) if overall_avg != 0 else 0,
                        "priority": "medium",
                    })

        opportunities.sort(key=lambda x: 0 if x["priority"] == "high" else 1)
        return opportunities[:30]

    def _generate_executive_report(self, insights: dict) -> str:
        """Use Claude to generate a polished executive report from raw insights."""
        insights_summary = self._format_insights_for_llm(insights)

        response = self.client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=8000,
            messages=[{"role": "user", "content": f"""Genera un reporte ejecutivo en Markdown para el equipo de operaciones de Rappi.

DATOS DE CONTEXTO:
- Paises: {', '.join(self.summary['countries'])}
- Metricas: {', '.join(self.summary['metrics'])}
- Periodo: 9 semanas rolling (L8W mas antigua, L0W mas reciente)

INSIGHTS DETECTADOS:
{insights_summary}

FORMATO DEL REPORTE:
1. **Resumen Ejecutivo** (3-5 bullet points con los hallazgos mas criticos)
2. **Anomalias Detectadas** (tabla con las anomalias mas relevantes y su impacto)
3. **Tendencias Preocupantes** (tendencias negativas que requieren atencion inmediata)
4. **Benchmarking** (comparacion entre paises, zonas wealthy vs non-wealthy, priorizadas vs no)
5. **Correlaciones Clave** (relaciones entre metricas que revelan dinamicas operacionales)
6. **Oportunidades Identificadas** (acciones concretas con potencial de impacto)
7. **Recomendaciones Accionables** (top 5-7 acciones priorizadas por impacto y urgencia)

REGLAS:
- Escribe en espanol profesional
- Usa tablas markdown donde sea apropiado
- Se especifico con datos y porcentajes
- Cada recomendacion debe ser accionable y medible
- Incluye el contexto de negocio de Rappi
- El tono debe ser ejecutivo pero accesible
"""}],
        )

        return response.content[0].text

    def _format_insights_for_llm(self, insights: dict) -> str:
        """Format raw insights into a readable string for the LLM."""
        parts = []

        parts.append("=== ANOMALIAS ===")
        for a in insights["anomalies"][:15]:
            if a["type"] == "statistical_outlier":
                parts.append(f"- [{a['severity'].upper()}] {a['metric']} en {a['country']}/{a['city']}/{a['zone']}: "
                             f"valor={a['value']}, media={a['mean']}, z-score={a['z_score']}, "
                             f"direccion={a['direction']}")
            else:
                parts.append(f"- [{a['severity'].upper()}] Cambio subito en {a['metric']} "
                             f"({a['country']}/{a['city']}/{a['zone']}): "
                             f"de {a.get('prev_value', 'N/A')} a {a['value']} (cambio={a.get('change', 'N/A')})")

        parts.append("\n=== TENDENCIAS PREOCUPANTES ===")
        for t in insights["concerning_trends"][:15]:
            parts.append(f"- [{t['severity'].upper()}] {t['metric']} en {t['group_by']}={t['group_value']}: "
                         f"cambio total={t['total_change_pct']}%, "
                         f"deterioro consecutivo={t['consecutive_deterioration_weeks']} semanas, "
                         f"slope={t['slope']}")

        parts.append("\n=== BENCHMARKING ===")
        for b in insights["benchmarking"][:15]:
            if b["type"] == "country_benchmark":
                parts.append(f"- {b['metric']}: Mejor={b['best_performer']}({b['best_value']}), "
                             f"Peor={b['worst_performer']}({b['worst_value']}), Gap={b['gap']}")
            elif b["type"] == "zone_type_benchmark":
                parts.append(f"- {b['metric']}: Wealthy={b['wealthy_avg']}, "
                             f"Non-Wealthy={b['non_wealthy_avg']}, Gap={b['gap']} ({b['gap_pct']}%)")

        parts.append("\n=== CORRELACIONES ===")
        for c in insights["correlations"][:10]:
            parts.append(f"- {c['metric_1']} <-> {c['metric_2']}: r={c['correlation']} "
                         f"({c['strength']}, {c['direction']})")

        parts.append("\n=== OPORTUNIDADES ===")
        for o in insights["opportunities"][:15]:
            if o["type"] == "underperforming_priority_zone":
                parts.append(f"- [{o['priority'].upper()}] Zona prioritaria bajo rendimiento: "
                             f"{o['metric']} en {o['country']}/{o['city']}/{o['zone']} "
                             f"(valor={o['value']}, benchmark={o['benchmark']})")
            elif o["type"] == "momentum_opportunity":
                parts.append(f"- [{o['priority'].upper()}] Momentum positivo: {o['metric']} en "
                             f"{o['country']}/{o['city']}/{o['zone']} (+{o['wow_improvement']}% WoW)")
            elif o["type"] == "adoption_gap":
                parts.append(f"- [{o['priority'].upper()}] Gap de adopcion: {o['metric']} en "
                             f"{o['country']}/{o['city']}/{o['zone']} "
                             f"(actual={o['current_adoption']}, promedio={o['average_adoption']}, "
                             f"gap={o['gap_pct']}%)")

        return "\n".join(parts)
