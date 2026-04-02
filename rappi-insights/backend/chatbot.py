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

REGLAS:
1. Responde SIEMPRE en espanol, de forma clara y accionable.
2. Cuando el usuario pregunte sobre datos, usa la funcion analyze_data para obtener los datos reales.
3. Proporciona contexto de negocio: explica que significa cada metrica y por que importa.
4. Cuando identifiques tendencias, se especifico con numeros y porcentajes.
5. Sugiere preguntas de seguimiento relevantes al final de cada respuesta.
6. Si el usuario pregunta algo que no puedes responder con los datos disponibles, dilo claramente.
7. Usa formato markdown para tablas y listas cuando sea apropiado.
8. Recuerda el contexto de la conversacion para respuestas coherentes.

CONTEXTO DE NEGOCIO RAPPI:
- Rappi opera en 9 paises de LATAM: AR, BR, CL, CO, CR, EC, MX, PE, UY
- Las zonas se clasifican en Wealthy/Non Wealthy y por priorizacion
- Las metricas cubren: eficiencia operacional, conversion, adopcion de productos, rentabilidad
- Los datos cubren 9 semanas rolling (L8W mas antigua a L0W mas reciente)
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
    }
]


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
            "¿Cual es el pais con mas ordenes esta semana?",
            "¿Como ha evolucionado Perfect Orders en Colombia?",
            "Compara las zonas Wealthy vs Non Wealthy en metricas de conversion",
            "¿Cuales son las 5 ciudades con peor % Order Loss?",
            "¿Que correlacion existe entre Pro Adoption y Gross Profit?",
            "Muestra las tendencias de Turbo Adoption por pais",
            "¿Que zonas priorizadas tienen peor rendimiento?",
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
