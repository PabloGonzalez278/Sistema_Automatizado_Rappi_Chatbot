"""
FastAPI Backend - API para el Sistema de Analisis Inteligente de Rappi.
"""
import os
import io
import csv
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
from email import encoders
from typing import Any
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, StreamingResponse
from pydantic import BaseModel
from dotenv import load_dotenv

load_dotenv()

from chatbot import RappiChatbot
from insights_engine import InsightsEngine
from data_loader import get_data_summary, query_data, WEEK_LABELS

app = FastAPI(
    title="Rappi Insights API",
    description="Sistema de Analisis Inteligente para Operaciones de Rappi",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

API_KEY = os.getenv("OPENAI_API_KEY", "")

_chatbot = None
_insights_engine = None


def get_chatbot():
    global _chatbot
    if _chatbot is None:
        if not API_KEY:
            raise HTTPException(status_code=500, detail="OPENAI_API_KEY not configured. Create a .env file with OPENAI_API_KEY=your-key")
        _chatbot = RappiChatbot(api_key=API_KEY)
    return _chatbot


def get_insights_engine():
    global _insights_engine
    if _insights_engine is None:
        if not API_KEY:
            raise HTTPException(status_code=500, detail="OPENAI_API_KEY not configured. Create a .env file with OPENAI_API_KEY=your-key")
        _insights_engine = InsightsEngine(api_key=API_KEY)
    return _insights_engine


class ChatRequest(BaseModel):
    message: str


class ChatResponse(BaseModel):
    response: str
    suggestions: list[str]
    chart_data: dict | None = None


class DataQueryRequest(BaseModel):
    dataset: str = "metrics"
    countries: list[str] | None = None
    cities: list[str] | None = None
    metrics: list[str] | None = None
    zone_types: list[str] | None = None


@app.get("/")
def root():
    return {"message": "Rappi Insights API", "version": "1.0.0"}


@app.get("/api/health")
def health():
    return {"status": "ok", "api_key_configured": bool(API_KEY)}


@app.get("/api/data/summary")
def data_summary():
    return get_data_summary()


@app.post("/api/chat", response_model=ChatResponse)
def chat(request: ChatRequest):
    bot = get_chatbot()
    result = bot.chat(request.message)
    return ChatResponse(**result)


@app.post("/api/chat/reset")
def reset_chat():
    global _chatbot
    _chatbot = None
    return {"status": "ok", "message": "Conversacion reiniciada"}


@app.get("/api/chat/suggestions")
def get_suggestions():
    bot = get_chatbot()
    return {"suggestions": bot.get_suggestions()}


@app.post("/api/insights/report")
def generate_report():
    engine = get_insights_engine()
    result = engine.generate_full_report()
    return result


@app.get("/api/insights/report/html")
def generate_report_html():
    """Generate report and return as styled HTML."""
    import markdown
    engine = get_insights_engine()
    result = engine.generate_full_report()

    html_content = markdown.markdown(
        result["report_markdown"],
        extensions=["tables", "fenced_code", "toc"],
    )

    styled_html = f"""<!DOCTYPE html>
<html lang="es">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Reporte Ejecutivo Rappi</title>
    <style>
        body {{ font-family: 'Segoe UI', sans-serif; max-width: 900px; margin: 0 auto; padding: 40px; color: #333; line-height: 1.6; }}
        h1 {{ color: #FF441F; border-bottom: 3px solid #FF441F; padding-bottom: 10px; }}
        h2 {{ color: #1a1a2e; margin-top: 30px; border-bottom: 1px solid #eee; padding-bottom: 8px; }}
        h3 {{ color: #FF441F; }}
        table {{ border-collapse: collapse; width: 100%; margin: 15px 0; }}
        th {{ background: #FF441F; color: white; padding: 10px 12px; text-align: left; }}
        td {{ padding: 8px 12px; border-bottom: 1px solid #eee; }}
        tr:nth-child(even) {{ background: #f9f9f9; }}
        code {{ background: #f4f4f4; padding: 2px 6px; border-radius: 3px; }}
        blockquote {{ border-left: 4px solid #FF441F; padding: 10px 15px; background: #fff5f3; margin: 15px 0; }}
        ul, ol {{ padding-left: 20px; }}
        li {{ margin: 5px 0; }}
        .header {{ text-align: center; margin-bottom: 30px; }}
        .footer {{ text-align: center; color: #999; font-size: 0.85em; margin-top: 50px; border-top: 1px solid #eee; padding-top: 15px; }}
    </style>
</head>
<body>
    <div class="header">
        <h1>Reporte Ejecutivo de Operaciones</h1>
        <p>Generado: {result['generated_at']}</p>
    </div>
    {html_content}
    <div class="footer">
        <p>Sistema de Analisis Inteligente para Operaciones de Rappi - Generado con IA</p>
    </div>
</body>
</html>"""

    return HTMLResponse(content=styled_html)


@app.post("/api/data/query")
def query(request: DataQueryRequest):
    df = query_data(
        dataset=request.dataset,
        countries=request.countries,
        cities=request.cities,
        metrics=request.metrics,
        zone_types=request.zone_types,
    )
    return {
        "count": len(df),
        "data": df.head(100).to_dict(orient="records"),
    }


# ─── BONUS: Export endpoints ───────────────────────────────────────

class ExportCSVRequest(BaseModel):
    dataset: str = "metrics"
    countries: list[str] | None = None
    cities: list[str] | None = None
    metrics: list[str] | None = None
    zone_types: list[str] | None = None


@app.post("/api/export/csv")
def export_csv(request: ExportCSVRequest):
    """Export filtered data as CSV file."""
    df = query_data(
        dataset=request.dataset,
        countries=request.countries,
        cities=request.cities,
        metrics=request.metrics,
        zone_types=request.zone_types,
    )
    stream = io.StringIO()
    df.to_csv(stream, index=False)
    stream.seek(0)
    return StreamingResponse(
        iter([stream.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename=rappi_export_{request.dataset}.csv"},
    )


@app.post("/api/export/report-csv")
def export_report_csv():
    """Export executive report insights as CSV."""
    engine = get_insights_engine()
    result = engine.generate_full_report()
    raw = result.get("raw_insights", {})

    stream = io.StringIO()
    writer = csv.writer(stream)

    # Write anomalies
    writer.writerow(["SECCION", "PAIS", "CIUDAD", "ZONA", "METRICA", "VALOR", "DETALLE"])
    for item in raw.get("anomalies", []):
        writer.writerow([
            "Anomalia",
            item.get("country", ""),
            item.get("city", ""),
            item.get("zone", ""),
            item.get("metric", ""),
            item.get("value", ""),
            item.get("detail", item.get("type", "")),
        ])
    for item in raw.get("concerning_trends", []):
        writer.writerow([
            "Tendencia Preocupante",
            item.get("country", ""),
            item.get("city", ""),
            item.get("zone", ""),
            item.get("metric", ""),
            item.get("value", ""),
            item.get("detail", item.get("type", "")),
        ])
    for item in raw.get("opportunities", []):
        writer.writerow([
            "Oportunidad",
            item.get("country", ""),
            item.get("city", ""),
            item.get("zone", ""),
            item.get("metric", ""),
            item.get("value", ""),
            item.get("detail", item.get("type", "")),
        ])

    stream.seek(0)
    return StreamingResponse(
        iter([stream.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=rappi_reporte_insights.csv"},
    )


# ─── BONUS: Email endpoint ────────────────────────────────────────

class EmailRequest(BaseModel):
    to_email: str
    subject: str = "Reporte Ejecutivo Rappi - Insights Automaticos"
    include_report: bool = True


@app.post("/api/email/send-report")
def send_report_email(request: EmailRequest):
    """Send executive report via email using SMTP."""
    smtp_host = os.getenv("SMTP_HOST", "smtp.gmail.com")
    smtp_port = int(os.getenv("SMTP_PORT", "587"))
    smtp_user = os.getenv("SMTP_USER", "")
    smtp_password = os.getenv("SMTP_PASSWORD", "")
    from_email = os.getenv("SMTP_FROM", smtp_user)

    if not smtp_user or not smtp_password:
        raise HTTPException(
            status_code=500,
            detail="Configuracion SMTP no encontrada. Agrega SMTP_HOST, SMTP_PORT, SMTP_USER, SMTP_PASSWORD en .env"
        )

    # Generate report
    engine = get_insights_engine()
    result = engine.generate_full_report()
    report_md = result["report_markdown"]

    # Build HTML version
    import markdown
    html_body = markdown.markdown(report_md, extensions=["tables", "fenced_code"])

    # Create email
    msg = MIMEMultipart("alternative")
    msg["From"] = from_email
    msg["To"] = request.to_email
    msg["Subject"] = request.subject

    # Plain text version
    msg.attach(MIMEText(report_md, "plain", "utf-8"))

    # HTML version with styling
    styled_html = f"""<html>
<head><style>
    body {{ font-family: 'Segoe UI', sans-serif; color: #333; line-height: 1.6; padding: 20px; }}
    h1 {{ color: #FF441F; }} h2 {{ color: #1a1a2e; }} h3 {{ color: #FF441F; }}
    table {{ border-collapse: collapse; width: 100%; margin: 10px 0; }}
    th {{ background: #FF441F; color: white; padding: 8px 12px; text-align: left; }}
    td {{ padding: 6px 12px; border-bottom: 1px solid #eee; }}
</style></head>
<body>{html_body}</body></html>"""
    msg.attach(MIMEText(styled_html, "html", "utf-8"))

    # Attach MD file
    md_attachment = MIMEBase("application", "octet-stream")
    md_attachment.set_payload(report_md.encode("utf-8"))
    encoders.encode_base64(md_attachment)
    md_attachment.add_header("Content-Disposition", "attachment", filename="reporte_rappi.md")
    msg.attach(md_attachment)

    try:
        with smtplib.SMTP(smtp_host, smtp_port) as server:
            server.starttls()
            server.login(smtp_user, smtp_password)
            server.send_message(msg)
        return {"status": "ok", "message": f"Reporte enviado exitosamente a {request.to_email}"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error al enviar email: {str(e)}")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
