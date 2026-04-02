# Sistema de Analisis Inteligente para Operaciones de Rappi

Sistema basado en IA que democratiza el acceso a datos operacionales y automatiza la generacion de insights accionables para Rappi.

## Arquitectura

```
┌─────────────────────────────────────────────────────────┐
│                    FRONTEND (React)                      │
│  ┌──────────────────┐  ┌─────────────────────────────┐  │
│  │ Bot Conversacional│  │  Visor de Reporte Ejecutivo │  │
│  │  (ChatView)       │  │  (ReportView)               │  │
│  └────────┬─────────┘  └────────────┬────────────────┘  │
└───────────┼─────────────────────────┼────────────────────┘
            │         HTTP/REST       │
┌───────────┼─────────────────────────┼────────────────────┐
│           ▼      BACKEND (FastAPI)  ▼                    │
│  ┌──────────────────┐  ┌─────────────────────────────┐  │
│  │   Chatbot Module  │  │   Insights Engine           │  │
│  │  (Claude + Tools) │  │  (Analisis Automatico)      │  │
│  └────────┬─────────┘  └────────────┬────────────────┘  │
│           │                         │                    │
│  ┌────────▼─────────────────────────▼────────────────┐  │
│  │              Data Loader (Pandas)                  │  │
│  │     Carga, limpia y transforma datos Excel         │  │
│  └────────────────────┬──────────────────────────────┘  │
└───────────────────────┼──────────────────────────────────┘
                        │
              ┌─────────▼─────────┐
              │   rappi_data.xlsx  │
              │  (RAW_INPUT_METRICS│
              │   RAW_ORDERS)      │
              └───────────────────┘
```

## Productos

### Producto 1: Bot Conversacional de Datos

Chatbot para usuarios no tecnicos que permite hacer preguntas en lenguaje natural sobre metricas operacionales.

**Capacidades:**
- **Filtrado**: "¿Cual es el Perfect Orders en Bogota?"
- **Comparaciones**: "Compara zonas Wealthy vs Non Wealthy en conversion"
- **Tendencias**: "¿Como ha evolucionado el % Order Loss en Brasil?"
- **Agregaciones**: "¿Cual es el promedio de Gross Profit por pais?"
- **Analisis multivariable**: "¿Que correlacion hay entre Pro Adoption y ordenes?"
- **Inferencia**: "¿Que zonas priorizadas tienen peor rendimiento?"

**Caracteristicas:**
- Contexto de negocio Rappi integrado (el bot entiende las metricas)
- Sugerencias de preguntas contextuales
- Memoria conversacional (recuerda preguntas anteriores)
- Respuestas con formato markdown (tablas, listas, negritas)

### Producto 2: Sistema de Insights Automaticos

Analisis automatico que genera un reporte ejecutivo completo con:

1. **Deteccion de anomalias**: Z-score estadistico para identificar valores atipicos y cambios subitos
2. **Tendencias preocupantes**: Deterioro consecutivo por 3+ semanas, slopes negativos significativos
3. **Benchmarking**: Comparacion entre paises, Wealthy vs Non-Wealthy, priorizadas vs no priorizadas
4. **Correlaciones**: Matriz de correlacion entre metricas y con volumen de ordenes
5. **Oportunidades**: Zonas prioritarias bajo rendimiento, gaps de adopcion, momentum positivo
6. **Recomendaciones accionables**: Top acciones priorizadas por impacto y urgencia

**Salida**: Markdown, HTML con estilos Rappi

## Stack Tecnologico

| Componente | Tecnologia | Justificacion |
|-----------|-----------|---------------|
| **LLM** | OpenAI | Alta capacidad de razonamiento, tool use nativo, excelente espanol |
| **Backend** | Python + FastAPI | Ecosistema de datos maduro (Pandas/NumPy), async, tipado |
| **Frontend** | React | Componentes reutilizables, ecosystem robusto, renderizado markdown |
| **Datos** | Pandas + NumPy | Transformaciones eficientes, analisis estadistico built-in |
| **Integracion LLM** | Anthropic SDK + Tool Use | Permite al LLM ejecutar analisis reales sobre datos reales |

### Decisiones de Diseno

- **Tool Use vs RAG**: Se eligio Tool Use porque permite al LLM ejecutar queries dinamicas y calculos precisos sobre los datos reales, en vez de depender de embeddings que pueden perder precision numerica.
- **Sonnet vs Opus**: Sonnet ofrece el mejor balance costo/velocidad/calidad para queries interactivas. Opus se reservaria para analisis mas complejos.
- **Pandas en backend**: Los datos caben en memoria (~12K rows), no se necesita base de datos. Pandas es optimo para transformaciones analiticas.
- **FastAPI**: Soporte nativo async, validacion con Pydantic, documentacion automatica OpenAPI.

## Instalacion y Ejecucion

### Prerrequisitos

- Python 3.11+
- Node.js 18+
- API Key de OpenAI

### 1. Backend

```bash
cd rappi-insights/backend
pip install -r requirements.txt

# Configurar API key
cp .env.example .env
# Editar .env y agregar tu OPENAI
_API_KEY

# Ejecutar
python main.py
```

El backend estara disponible en `http://localhost:8000`

Documentacion API automatica: `http://localhost:8000/docs`

### 2. Frontend

```bash
cd rappi-insights/frontend
npm install
npm start
```

El frontend estara disponible en `http://localhost:3000`

### 3. Verificar

1. Abre `http://localhost:3000`
2. En el **Bot Conversacional**, haz una pregunta como "¿Cuantas ordenes tiene Colombia?"
3. En **Reporte Ejecutivo**, haz clic en "Generar Reporte"

## Estructura del Proyecto

```
rappi-insights/
├── backend/
│   ├── main.py              # FastAPI app, endpoints REST
│   ├── data_loader.py       # Carga y transformacion de datos Excel
│   ├── chatbot.py           # Bot conversacional con Claude + Tool Use
│   ├── insights_engine.py   # Motor de insights automaticos
│   ├── requirements.txt     # Dependencias Python
│   ├── .env.example         # Template de configuracion
│   └── .env                 # Configuracion (no versionado)
├── frontend/
│   ├── public/
│   │   └── index.html
│   ├── src/
│   │   ├── App.js           # Componente principal con routing
│   │   ├── components/
│   │   │   ├── Sidebar.js   # Navegacion lateral
│   │   │   ├── ChatView.js  # Interfaz del chatbot
│   │   │   └── ReportView.js# Visor de reportes
│   │   └── index.js         # Entry point React
│   └── package.json
├── data/
│   └── rappi_data.xlsx      # Datos operacionales
└── README.md
```

## API Endpoints

| Metodo | Endpoint | Descripcion |
|--------|----------|-------------|
| GET | `/api/health` | Health check y estado de configuracion |
| GET | `/api/data/summary` | Resumen de dimensiones disponibles |
| POST | `/api/chat` | Enviar mensaje al chatbot |
| POST | `/api/chat/reset` | Reiniciar conversacion |
| GET | `/api/chat/suggestions` | Obtener preguntas sugeridas |
| POST | `/api/insights/report` | Generar reporte ejecutivo (JSON+Markdown) |
| GET | `/api/insights/report/html` | Generar reporte como HTML estilizado |
| POST | `/api/data/query` | Query directo a los datos |

## Datos

El sistema trabaja con dos datasets:

- **RAW_INPUT_METRICS** (12,574 filas): 13 metricas operacionales por pais/ciudad/zona a lo largo de 9 semanas rolling
- **RAW_ORDERS** (1,243 filas): Volumen de ordenes por pais/ciudad/zona, 9 semanas rolling

### Metricas disponibles

| Metrica | Descripcion | Interpretacion |
|---------|-------------|----------------|
| Perfect Orders | % ordenes completadas sin issues | Mayor = mejor |
| % Order Loss | % ordenes perdidas/canceladas | Menor = mejor |
| Gross Profit UE | Ganancia bruta por unidad economica | Mayor = mejor |
| Pro Adoption | % usuarios con Rappi Pro | Mayor = mejor |
| Turbo Adoption | % ordenes usando Rappi Turbo | Mayor = mejor |
| Lead Penetration | % conversion desde leads | Mayor = mejor |
| Restaurants SST > SS CVR | Conversion search-to-store restaurantes | Mayor = mejor |
| Retail SST > SS CVR | Conversion search-to-store retail | Mayor = mejor |
| Restaurants SS > ATC CVR | Conversion store-to-cart restaurantes | Mayor = mejor |
| Restaurants Markdowns / GMV | Ratio de descuentos en restaurantes | Depende del contexto |
| % Restaurants Sessions With Optimal Assortment | Completitud de menu | Mayor = mejor |
| MLTV Top Verticals Adoption | Adopcion multi-vertical | Mayor = mejor |
| Non-Pro PTC > OP | Conversion purchase-to-order (no Pro) | Mayor = mejor |
| % PRO Users Who Breakeven | % usuarios Pro que recuperan costo | Mayor = mejor |

## Limitaciones y Proximos Pasos

### Limitaciones actuales
- Datos estaticos (snapshot Excel, no conexion en tiempo real)
- Sin autenticacion de usuarios
- Sin persistencia de conversaciones entre sesiones
- Visualizaciones limitadas a texto/markdown (sin graficos interactivos)

### Proximos pasos con mas tiempo
1. **Visualizaciones interactivas**: Integrar Recharts/D3.js para graficos de tendencias y mapas de calor
2. **Conexion a datos en vivo**: API directa al data warehouse de Rappi
3. **Alertas proactivas**: Sistema de notificaciones cuando se detecten anomalias
4. **Multi-usuario**: Autenticacion y personalizacion por rol (ops, producto, finanzas)
5. **Exportacion a PDF**: Reportes ejecutivos con formato profesional para presentaciones
6. **Cache inteligente**: Cachear analisis frecuentes para reducir latencia y costos de API
7. **Historico de insights**: Tracking de insights over time para medir si las recomendaciones tuvieron impacto
