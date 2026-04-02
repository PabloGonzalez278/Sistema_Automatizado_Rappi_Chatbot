"""
Chatbot Module - Bot conversacional de datos para Rappi usando OpenAI GPT.
Maneja consultas en lenguaje natural sobre metricas operacionales.
"""
import json
from openai import OpenAI
import pandas as pd
import numpy as np
from data_loader import (
    load_metrics_wide, load_orders_wide, query_data,
    compute_trends, get_context_for_llm, get_data_summary,
    WEEK_LABELS,
)

SYSTEM_PROMPT = """Eres un analista de datos experto de Rappi, la super-app de delivery lider en Latinoamerica.
Tu rol es ayudar a usuarios no tecnicos a entender las metricas operacionales de Rappi.

REGLAS CRITICAS:
1. Responde SIEMPRE en espanol, de forma clara y accionable.
2. SIEMPRE usa las herramientas (analyze_data o cross_metric_analysis) para obtener datos reales antes de responder. NUNCA inventes datos.
3. Para preguntas complejas, puedes hacer MULTIPLES llamadas a herramientas para obtener toda la informacion necesaria.
4. Proporciona contexto de negocio: explica que significa cada metrica y por que importa para Rappi.
5. Cuando identifiques tendencias, se especifico con numeros y porcentajes exactos.
6. Usa formato markdown: tablas para comparaciones, listas para rankings, negritas para datos clave.
7. Al final de cada respuesta, sugiere 2-3 preguntas de seguimiento relevantes.
8. Recuerda el contexto de la conversacion para respuestas coherentes.

ESTRATEGIA POR TIPO DE PREGUNTA:
- FILTRADO ("cuales son las top/mejores/peores X"): Usa analyze_data con analysis_type="ranking", group_by apropiado y top_n
- COMPARACIONES ("compara X vs Y"): Usa analyze_data con analysis_type="comparison" y group_by por la dimension a comparar
- TENDENCIAS ("evolucion/tendencia de X"): Usa analyze_data con analysis_type="trend" y filtra por la entidad especifica
- AGREGACIONES ("promedio/total de X por Y"): Usa analyze_data con analysis_type="summary" y group_by
- MULTIVARIABLE ("zonas con alto X pero bajo Y"): Usa cross_metric_analysis para cruzar dos metricas
- INFERENCIA ("que explica/por que"): Combina multiples llamadas: primero datos de ordenes, luego metricas relevantes, y usa tu conocimiento de negocio para inferir causas

CONTEXTO DE NEGOCIO RAPPI:
- Rappi opera en 9 paises de LATAM: AR, BR, CL, CO, CR, EC, MX, PE, UY
- Las zonas se clasifican en Wealthy/Non Wealthy y por priorizacion (High Priority, Prioritized, Not Prioritized)
- Las metricas cubren: eficiencia operacional, conversion, adopcion de productos, rentabilidad
- Los datos cubren 9 semanas rolling (L8W=8 semanas atras, L0W=semana mas reciente/actual)
- Perfect Orders: % de ordenes sin problemas (mayor=mejor)
- % Order Loss: ordenes perdidas (menor=mejor)
- Gross Profit UE: ganancia bruta unitaria
- Lead Penetration: conversion desde leads (mayor=mejor)
- Pro Adoption: usuarios con Rappi Pro
- Turbo Adoption: ordenes con delivery rapido
- Restaurants SST>SS CVR: conversion busqueda-a-tienda en restaurantes
- Retail SST>SS CVR: conversion busqueda-a-tienda en retail
"""

# OpenAI function calling format
TOOLS_OPENAI = [
    {
        "type": "function",
        "function": {
            "name": "analyze_data",
            "description": "Analiza datos operacionales de Rappi. Usa esta herramienta para responder preguntas sobre metricas, ordenes, tendencias y comparaciones. Puedes filtrar por pais, ciudad, zona, tipo de metrica, tipo de zona y priorizacion. El analisis puede incluir: filtrado, agregacion, comparacion, tendencias, rankings, y correlaciones.",
            "parameters": {
                "type": "object",
                "properties": {
                    "dataset": {
                        "type": "string",
                        "enum": ["metrics", "orders"],
                        "description": "Dataset a consultar: 'metrics' para metricas operacionales, 'orders' para volumen de ordenes"
                    },
                    "countries": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Filtro de paises (codigos: AR, BR, CL, CO, CR, EC, MX, PE, UY)"
                    },
                    "cities": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Filtro de ciudades"
                    },
                    "zones": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Filtro de zonas especificas"
                    },
                    "metrics": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Filtro de metricas especificas"
                    },
                    "zone_types": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Filtro por tipo de zona: Wealthy, Non Wealthy"
                    },
                    "zone_prioritizations": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Filtro por priorizacion: High Priority, Prioritized, Not Prioritized"
                    },
                    "analysis_type": {
                        "type": "string",
                        "enum": ["summary", "trend", "comparison", "ranking", "detail", "correlation"],
                        "description": "Tipo de analisis: summary (resumen), trend (tendencia temporal), comparison (comparar grupos), ranking (top/bottom), detail (datos detallados), correlation (correlaciones entre metricas)"
                    },
                    "group_by": {
                        "type": "string",
                        "enum": ["COUNTRY", "CITY", "ZONE", "METRIC", "ZONE_TYPE", "ZONE_PRIORITIZATION"],
                        "description": "Columna para agrupar resultados"
                    },
                    "top_n": {
                        "type": "integer",
                        "description": "Numero de resultados top/bottom a retornar (default: 10)"
                    },
                    "ascending": {
                        "type": "boolean",
                        "description": "Si true, ordena ascendente (peores primero). Default: false (mejores primero)"
                    }
                },
                "required": ["dataset", "analysis_type"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "cross_metric_analysis",
            "description": "Analisis multivariable: cruza dos metricas diferentes para encontrar zonas con combinaciones especificas (ej: alto Lead Penetration pero bajo Perfect Order, zonas con mayor crecimiento de ordenes). Tambien permite analizar crecimiento de ordenes en las ultimas N semanas.",
            "parameters": {
                "type": "object",
                "properties": {
                    "metric_1": {
                        "type": "string",
                        "description": "Primera metrica a analizar"
                    },
                    "metric_2": {
                        "type": "string",
                        "description": "Segunda metrica a analizar (opcional, omitir para analisis de crecimiento de ordenes)"
                    },
                    "condition": {
                        "type": "string",
                        "enum": ["high_low", "low_high", "both_high", "both_low", "top_growth", "bottom_growth"],
                        "description": "Condicion: high_low (metric_1 alta, metric_2 baja), low_high (inverso), both_high, both_low, top_growth (mayor crecimiento), bottom_growth (mayor caida)"
                    },
                    "countries": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Filtro de paises"
                    },
                    "top_n": {
                        "type": "integer",
                        "description": "Numero de resultados (default: 10)"
                    },
                    "weeks_back": {
                        "type": "integer",
                        "description": "Numero de semanas hacia atras para calcular crecimiento (default: 5)"
                    }
                },
                "required": ["condition"]
            }
        }
    }
]


def execute_cross_metric_analysis(params: dict) -> str:
    """Execute cross-metric analysis for multivariable queries."""
    condition = params.get("condition", "high_low")
    metric_1 = params.get("metric_1")
    metric_2 = params.get("metric_2")
    countries = params.get("countries")
    top_n = params.get("top_n", 10)
    weeks_back = params.get("weeks_back", 5)

    metrics_df = load_metrics_wide()
    orders_df = load_orders_wide()

    if countries:
        metrics_df = metrics_df[metrics_df["COUNTRY"].isin(countries)]
        orders_df = orders_df[orders_df["COUNTRY"].isin(countries)]

    week_cols_m = [c for c in metrics_df.columns if c.endswith("_ROLL")]
    week_cols_o = [c for c in orders_df.columns if c.startswith("L") and c.endswith("W")]

    result = []

    # Growth analysis for orders
    if condition in ["top_growth", "bottom_growth"]:
        latest_col = week_cols_o[-1]
        start_col = week_cols_o[-min(weeks_back, len(week_cols_o))]

        orders_df = orders_df.copy()
        orders_df["growth"] = orders_df[latest_col] - orders_df[start_col]
        orders_df["growth_pct"] = np.where(
            orders_df[start_col] != 0,
            (orders_df[latest_col] - orders_df[start_col]) / orders_df[start_col].abs() * 100,
            0
        )

        ascending = condition == "bottom_growth"
        sorted_df = orders_df.sort_values("growth_pct", ascending=ascending).head(top_n)

        direction = "mayor caida" if ascending else "mayor crecimiento"
        result.append(f"Zonas con {direction} en ordenes (ultimas {weeks_back} semanas):\n")

        for _, row in sorted_df.iterrows():
            result.append(f"  {row['COUNTRY']}/{row['CITY']}/{row['ZONE']}: "
                         f"{row[start_col]:,.0f} -> {row[latest_col]:,.0f} "
                         f"({row['growth_pct']:+.1f}%)")

            # Add weekly detail
            weekly = [f"{row[w]:,.0f}" for w in week_cols_o[-weeks_back:]]
            result.append(f"    Semanas: {' -> '.join(weekly)}")

        # If metric_1 provided, also show that metric for these zones
        if metric_1:
            result.append(f"\nMetrica '{metric_1}' para estas zonas:")
            for _, row in sorted_df.iterrows():
                mdata = metrics_df[(metrics_df["ZONE"] == row["ZONE"]) &
                                   (metrics_df["METRIC"] == metric_1)]
                if len(mdata) > 0:
                    mrow = mdata.iloc[0]
                    latest_m = mrow[week_cols_m[-1]]
                    start_m = mrow[week_cols_m[-min(weeks_back, len(week_cols_m))]]
                    change_m = latest_m - start_m
                    result.append(f"  {row['ZONE']}: {latest_m:.4f} (cambio: {change_m:+.4f})")

        return "\n".join(result)

    # Cross-metric analysis
    if not metric_1 or not metric_2:
        return "Se requieren metric_1 y metric_2 para analisis cruzado."

    latest_m = week_cols_m[-1]

    pivot = metrics_df.pivot_table(
        index=["COUNTRY", "CITY", "ZONE", "ZONE_TYPE", "ZONE_PRIORITIZATION"],
        columns="METRIC",
        values=latest_m,
        aggfunc="mean"
    ).reset_index()

    if metric_1 not in pivot.columns or metric_2 not in pivot.columns:
        available = [c for c in pivot.columns if c not in ["COUNTRY", "CITY", "ZONE", "ZONE_TYPE", "ZONE_PRIORITIZATION"]]
        return f"Metricas no encontradas. Disponibles: {', '.join(available)}"

    pivot = pivot.dropna(subset=[metric_1, metric_2])

    m1_median = pivot[metric_1].median()
    m2_median = pivot[metric_2].median()

    if condition == "high_low":
        filtered = pivot[(pivot[metric_1] > m1_median) & (pivot[metric_2] < m2_median)]
        desc = f"{metric_1} ALTO (>{m1_median:.4f}) y {metric_2} BAJO (<{m2_median:.4f})"
    elif condition == "low_high":
        filtered = pivot[(pivot[metric_1] < m1_median) & (pivot[metric_2] > m2_median)]
        desc = f"{metric_1} BAJO (<{m1_median:.4f}) y {metric_2} ALTO (>{m2_median:.4f})"
    elif condition == "both_high":
        filtered = pivot[(pivot[metric_1] > m1_median) & (pivot[metric_2] > m2_median)]
        desc = f"Ambas metricas ALTAS"
    elif condition == "both_low":
        filtered = pivot[(pivot[metric_1] < m1_median) & (pivot[metric_2] < m2_median)]
        desc = f"Ambas metricas BAJAS"
    else:
        filtered = pivot

    filtered = filtered.sort_values(metric_1, ascending=False).head(top_n)

    result.append(f"Analisis cruzado: {desc}")
    result.append(f"Mediana {metric_1}: {m1_median:.4f} | Mediana {metric_2}: {m2_median:.4f}")
    result.append(f"Zonas encontradas: {len(filtered)}\n")

    for _, row in filtered.iterrows():
        result.append(f"  {row['COUNTRY']}/{row['CITY']}/{row['ZONE']} ({row['ZONE_TYPE']}, {row['ZONE_PRIORITIZATION']}):")
        result.append(f"    {metric_1}: {row[metric_1]:.4f} | {metric_2}: {row[metric_2]:.4f}")

    # Correlation between the two
    corr = pivot[metric_1].corr(pivot[metric_2])
    result.append(f"\nCorrelacion entre {metric_1} y {metric_2}: {corr:.3f}")

    return "\n".join(result)


def execute_analysis(params: dict) -> str:
    """Execute data analysis based on tool parameters."""
    dataset = params.get("dataset", "metrics")
    analysis_type = params.get("analysis_type", "summary")
    group_by = params.get("group_by")
    top_n = params.get("top_n", 10)
    ascending = params.get("ascending", False)

    df = query_data(
        dataset=dataset,
        countries=params.get("countries"),
        cities=params.get("cities"),
        zones=params.get("zones"),
        metrics=params.get("metrics"),
        zone_types=params.get("zone_types"),
        zone_prioritizations=params.get("zone_prioritizations"),
    )

    if df.empty:
        return "No se encontraron datos con los filtros especificados."

    if dataset == "orders":
        week_cols = [c for c in df.columns if c.startswith("L") and c.endswith("W")]
    else:
        week_cols = [c for c in df.columns if c.endswith("_ROLL")]

    if analysis_type == "summary":
        return _summary_analysis(df, week_cols, group_by, dataset)
    elif analysis_type == "trend":
        return _trend_analysis(df, week_cols, group_by, dataset)
    elif analysis_type == "comparison":
        return _comparison_analysis(df, week_cols, group_by, dataset)
    elif analysis_type == "ranking":
        return _ranking_analysis(df, week_cols, group_by, top_n, ascending, dataset)
    elif analysis_type == "detail":
        return _detail_analysis(df, week_cols, dataset)
    elif analysis_type == "correlation":
        return _correlation_analysis(params)
    else:
        return _summary_analysis(df, week_cols, group_by, dataset)


def _summary_analysis(df, week_cols, group_by, dataset):
    result = []
    latest = week_cols[-1]
    prev = week_cols[-2] if len(week_cols) >= 2 else None

    if group_by and group_by in df.columns:
        grouped = df.groupby(group_by)
        stats = []
        for name, group in grouped:
            row = {"group": name, "count": len(group), "avg_latest": group[latest].mean()}
            if prev:
                row["avg_prev"] = group[prev].mean()
                row["wow_change"] = row["avg_latest"] - row["avg_prev"]
            stats.append(row)
        stats_df = pd.DataFrame(stats).sort_values("avg_latest", ascending=False)
        result.append(f"Resumen agrupado por {group_by} ({len(stats_df)} grupos):\n")
        result.append(stats_df.to_string(index=False, float_format="%.4f"))
    else:
        if "METRIC" in df.columns:
            for metric in df["METRIC"].unique():
                mdf = df[df["METRIC"] == metric]
                vals = mdf[latest]
                result.append(f"\n{metric}:")
                result.append(f"  Registros: {len(mdf)}")
                result.append(f"  Promedio: {vals.mean():.4f}")
                result.append(f"  Mediana: {vals.median():.4f}")
                result.append(f"  Min: {vals.min():.4f} | Max: {vals.max():.4f}")
                result.append(f"  Std Dev: {vals.std():.4f}")
                if prev:
                    prev_avg = mdf[prev].mean()
                    change = vals.mean() - prev_avg
                    pct = (change / abs(prev_avg) * 100) if prev_avg != 0 else 0
                    result.append(f"  Cambio WoW: {change:+.4f} ({pct:+.2f}%)")
        else:
            vals = df[latest]
            result.append(f"Registros: {len(df)}")
            result.append(f"Total: {vals.sum():,.0f}")
            result.append(f"Promedio: {vals.mean():,.0f}")
            result.append(f"Min: {vals.min():,.0f} | Max: {vals.max():,.0f}")

    return "\n".join(result)


def _trend_analysis(df, week_cols, group_by, dataset):
    result = []
    df_with_trends = compute_trends(df, week_cols)

    if group_by and group_by in df.columns:
        trends = []
        for name, group in df_with_trends.groupby(group_by):
            weekly_avgs = [group[w].mean() for w in week_cols]
            trend_slope = np.mean(group["TREND_SLOPE"]) if "TREND_SLOPE" in group.columns else 0
            trends.append({
                "group": name,
                "weekly_values": weekly_avgs,
                "slope": trend_slope,
                "direction": "creciente" if trend_slope > 0.001 else ("decreciente" if trend_slope < -0.001 else "estable"),
                "total_change_pct": ((weekly_avgs[-1] - weekly_avgs[0]) / abs(weekly_avgs[0]) * 100) if weekly_avgs[0] != 0 else 0,
            })
        trends.sort(key=lambda x: abs(x["slope"]), reverse=True)
        result.append(f"Analisis de tendencias por {group_by}:\n")
        for t in trends[:15]:
            week_str = " -> ".join(f"{v:.4f}" for v in t["weekly_values"])
            result.append(f"{t['group']}: {t['direction']} (slope={t['slope']:.6f}, cambio total={t['total_change_pct']:+.2f}%)")
            result.append(f"  Semanas (L8W->L0W): {week_str}")
    else:
        if "METRIC" in df.columns:
            for metric in df["METRIC"].unique():
                mdf = df_with_trends[df_with_trends["METRIC"] == metric]
                weekly_avgs = [mdf[w].mean() for w in week_cols]
                slope = mdf["TREND_SLOPE"].mean()
                direction = "creciente" if slope > 0.001 else ("decreciente" if slope < -0.001 else "estable")
                result.append(f"\n{metric}: Tendencia {direction}")
                result.append(f"  Semanas: {' -> '.join(f'{v:.4f}' for v in weekly_avgs)}")
                result.append(f"  Slope promedio: {slope:.6f}")
        else:
            weekly_totals = [df[w].sum() for w in week_cols]
            result.append("Tendencia de ordenes totales:")
            result.append(f"  Semanas: {' -> '.join(f'{v:,.0f}' for v in weekly_totals)}")
            change = ((weekly_totals[-1] - weekly_totals[0]) / weekly_totals[0] * 100) if weekly_totals[0] != 0 else 0
            result.append(f"  Cambio total: {change:+.2f}%")

    return "\n".join(result)


def _comparison_analysis(df, week_cols, group_by, dataset):
    if not group_by or group_by not in df.columns:
        return "Se requiere un campo group_by para comparaciones."

    result = []
    latest = week_cols[-1]
    oldest = week_cols[0]

    groups = {}
    for name, group in df.groupby(group_by):
        groups[name] = {
            "count": len(group),
            "avg_latest": group[latest].mean(),
            "avg_oldest": group[oldest].mean(),
            "median_latest": group[latest].median(),
            "std_latest": group[latest].std(),
        }
        groups[name]["change"] = groups[name]["avg_latest"] - groups[name]["avg_oldest"]
        groups[name]["change_pct"] = (groups[name]["change"] / abs(groups[name]["avg_oldest"]) * 100) if groups[name]["avg_oldest"] != 0 else 0

    result.append(f"Comparacion por {group_by}:\n")
    comp_df = pd.DataFrame(groups).T
    comp_df = comp_df.sort_values("avg_latest", ascending=False)
    result.append(comp_df.to_string(float_format="%.4f"))

    return "\n".join(result)


def _ranking_analysis(df, week_cols, group_by, top_n, ascending, dataset):
    result = []
    latest = week_cols[-1]
    prev = week_cols[-2] if len(week_cols) >= 2 else None

    if group_by and group_by in df.columns:
        agg = df.groupby(group_by).agg({latest: "mean"}).reset_index()
        if prev:
            agg_prev = df.groupby(group_by).agg({prev: "mean"}).reset_index()
            agg = agg.merge(agg_prev, on=group_by)
            agg["WoW_Change"] = agg[latest] - agg[prev]

        agg = agg.sort_values(latest, ascending=ascending).head(top_n)
        direction = "Bottom" if ascending else "Top"
        result.append(f"{direction} {top_n} por {group_by} (semana mas reciente):\n")
        result.append(agg.to_string(index=False, float_format="%.4f"))
    else:
        if dataset == "orders":
            sort_col = latest
            df_sorted = df.sort_values(sort_col, ascending=ascending).head(top_n)
            result.append(f"{'Bottom' if ascending else 'Top'} {top_n} zonas por ordenes:\n")
            result.append(df_sorted[["COUNTRY", "CITY", "ZONE", latest]].to_string(index=False, float_format=",.0f"))
        else:
            for metric in df["METRIC"].unique()[:3]:
                mdf = df[df["METRIC"] == metric].sort_values(latest, ascending=ascending).head(top_n)
                result.append(f"\n{'Bottom' if ascending else 'Top'} {top_n} - {metric}:")
                cols = ["COUNTRY", "CITY", "ZONE", latest]
                if prev:
                    cols.append(prev)
                result.append(mdf[cols].to_string(index=False, float_format="%.4f"))

    return "\n".join(result)


def _detail_analysis(df, week_cols, dataset):
    result = []
    if len(df) > 50:
        result.append(f"Mostrando primeros 50 de {len(df)} registros:\n")
        df = df.head(50)

    cols = [c for c in df.columns if c not in week_cols]
    cols.extend(week_cols[-3:])
    result.append(df[cols].to_string(index=False, float_format="%.4f"))
    return "\n".join(result)


def _correlation_analysis(params):
    metrics_df = load_metrics_wide()
    orders_df = load_orders_wide()

    countries = params.get("countries")
    cities = params.get("cities")

    if countries:
        metrics_df = metrics_df[metrics_df["COUNTRY"].isin(countries)]
        orders_df = orders_df[orders_df["COUNTRY"].isin(countries)]
    if cities:
        metrics_df = metrics_df[metrics_df["CITY"].isin(cities)]
        orders_df = orders_df[orders_df["CITY"].isin(cities)]

    result = ["Analisis de correlacion entre metricas (valores L0W):\n"]

    metrics_pivot = metrics_df.pivot_table(
        index=["COUNTRY", "CITY", "ZONE"],
        columns="METRIC",
        values=metrics_df.columns[-1],
        aggfunc="mean"
    )

    if len(metrics_pivot.columns) >= 2:
        corr = metrics_pivot.corr()
        result.append("Matriz de correlacion:\n")
        result.append(corr.to_string(float_format="%.3f"))

        pairs = []
        for i in range(len(corr.columns)):
            for j in range(i + 1, len(corr.columns)):
                val = corr.iloc[i, j]
                if not np.isnan(val):
                    pairs.append((corr.columns[i], corr.columns[j], val))
        pairs.sort(key=lambda x: abs(x[2]), reverse=True)

        result.append("\nCorrelaciones mas fuertes:")
        for m1, m2, val in pairs[:10]:
            direction = "positiva" if val > 0 else "negativa"
            result.append(f"  {m1} <-> {m2}: {val:.3f} ({direction})")

    return "\n".join(result)


class RappiChatbot:
    def __init__(self, api_key: str):
        self.client = OpenAI(api_key=api_key)
        self.conversation_history: list[dict] = []
        self.data_context = get_context_for_llm()
        self.data_summary = get_data_summary()

    def get_suggestions(self) -> list[str]:
        return [
            "¿Cuales son las 5 zonas con mayor % Lead Penetration esta semana?",
            "Compara el Perfect Order entre zonas Wealthy y Non Wealthy en Mexico",
            "Muestra la evolucion de Gross Profit UE en Chapinero ultimas 8 semanas",
            "¿Cual es el promedio de Lead Penetration por pais?",
            "¿Que zonas tienen alto Lead Penetration pero bajo Perfect Order?",
            "¿Cuales son las zonas que mas crecen en ordenes en las ultimas 5 semanas?",
            "¿Que correlacion existe entre Pro Adoption y Gross Profit?",
            "Dame un resumen de las metricas de restaurantes en Mexico",
        ]

    def chat(self, user_message: str) -> dict:
        system_prompt = f"""{SYSTEM_PROMPT}

{self.data_context}

DATOS DISPONIBLES PARA FILTRAR:
- Paises: {', '.join(self.data_summary['countries'])}
- Metricas: {', '.join(self.data_summary['metrics'])}
- Tipos de zona: {', '.join(self.data_summary['zone_types'])}
- Priorizaciones: {', '.join(self.data_summary['zone_prioritizations'])}
"""

        self.conversation_history.append({"role": "user", "content": user_message})

        messages = [{"role": "system", "content": system_prompt}] + self.conversation_history

        response = self.client.chat.completions.create(
            model="gpt-4o",
            max_tokens=4096,
            messages=messages,
            tools=TOOLS_OPENAI,
            tool_choice="auto",
        )

        msg = response.choices[0].message

        # Process tool calls iteratively
        while msg.tool_calls:
            # Add assistant message with tool calls to history
            self.conversation_history.append({
                "role": "assistant",
                "content": msg.content,
                "tool_calls": [
                    {
                        "id": tc.id,
                        "type": "function",
                        "function": {
                            "name": tc.function.name,
                            "arguments": tc.function.arguments,
                        }
                    }
                    for tc in msg.tool_calls
                ]
            })

            # Execute each tool call and add results
            for tool_call in msg.tool_calls:
                args = json.loads(tool_call.function.arguments)
                if tool_call.function.name == "cross_metric_analysis":
                    result = execute_cross_metric_analysis(args)
                else:
                    result = execute_analysis(args)
                self.conversation_history.append({
                    "role": "tool",
                    "tool_call_id": tool_call.id,
                    "content": result,
                })

            # Call again with tool results
            messages = [{"role": "system", "content": system_prompt}] + self.conversation_history
            response = self.client.chat.completions.create(
                model="gpt-4o",
                max_tokens=4096,
                messages=messages,
                tools=TOOLS_OPENAI,
                tool_choice="auto",
            )
            msg = response.choices[0].message

        # Extract final text
        final_text = msg.content or ""
        self.conversation_history.append({"role": "assistant", "content": final_text})

        return {
            "response": final_text,
            "suggestions": self._generate_followup_suggestions(user_message, final_text),
        }

    def _generate_followup_suggestions(self, question: str, answer: str) -> list[str]:
        base_suggestions = [
            "¿Puedes profundizar mas en este analisis?",
            "¿Como se compara esto con otros paises?",
            "¿Cual es la tendencia de las ultimas semanas?",
        ]
        return base_suggestions[:3]

    def reset(self):
        self.conversation_history = []
