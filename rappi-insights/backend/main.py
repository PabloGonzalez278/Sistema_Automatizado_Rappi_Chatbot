"""
FastAPI Backend - API para el Sistema de Analisis Inteligente de Rappi.
"""
import os
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
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

API_KEY = os.getenv("ANTHROPIC_API_KEY", "")

_chatbot = None
_insights_engine = None


def get_chatbot():
    global _chatbot
    if _chatbot is None:
        if not API_KEY:
            raise HTTPException(status_code=500, detail="ANTHROPIC_API_KEY not configured. Create a .env file with ANTHROPIC_API_KEY=your-key")
        _chatbot = RappiChatbot(api_key=API_KEY)
    return _chatbot


def get_insights_engine():
    global _insights_engine
    if _insights_engine is None:
        if not API_KEY:
            raise HTTPException(status_code=500, detail="ANTHROPIC_API_KEY not configured. Create a .env file with ANTHROPIC_API_KEY=your-key")
        _insights_engine = InsightsEngine(api_key=API_KEY)
    return _insights_engine


class ChatRequest(BaseModel):
    message: str


class ChatResponse(BaseModel):
    response: str
    suggestions: list[str]


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


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
