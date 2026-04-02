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
│  │ (GPT-4o + Tools)  │  │  (Analisis Automatico)      │  │
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

Chatbot para usuarios no tecnicos que permite hacer preguntas en lenguaje natural sobre metricas operacionales. Utiliza GPT-4o con Function Calling para ejecutar analisis reales sobre los datos.

**Herramientas de IA disponibles:**

| Herramienta | Funcion |
|-------------|---------|
| `analyze_data` | Filtrado, agregacion, comparacion, tendencias, rankings y correlaciones sobre metricas y ordenes |
| `cross_metric_analysis` | Analisis multivariable cruzando dos metricas, deteccion de crecimiento/caida en ordenes por zona |

**Capacidades demostradas (6 casos de uso):**

| Caso de Uso | Pregunta de Ejemplo |
|-------------|---------------------|
| **Filtrado** | "¿Cuales son las 5 zonas con mayor % Lead Penetration esta semana?" |
| **Comparaciones** | "Compara el Perfect Order entre zonas Wealthy y Non Wealthy en Mexico" |
| **Tendencias temporales** | "Muestra la evolucion de Gross Profit UE en Chapinero ultimas 8 semanas" |
| **Agregaciones** | "¿Cual es el promedio de Lead Penetration por pais?" |
| **Analisis multivariable** | "¿Que zonas tienen alto Lead Penetration pero bajo Perfect Order?" |
| **Inferencia** | "¿Cuales son las zonas que mas crecen en ordenes en las ultimas 5 semanas y que podria explicar el crecimiento?" |

**Caracteristicas adicionales:**
- Contexto de negocio Rappi integrado (el bot entiende cada metrica y su impacto)
- Sugerencias de preguntas contextuales (8 preguntas iniciales + 3 de seguimiento)
- Memoria conversacional (recuerda preguntas anteriores en la sesion)
- Respuestas con formato markdown (tablas, listas, negritas)
- Estrategia de analisis por tipo de pregunta documentada en el system prompt

### Producto 2: Sistema de Insights Automaticos

Analisis automatico que genera un reporte ejecutivo completo con:

1. **Deteccion de anomalias**: Z-score estadistico (umbral >2) para identificar valores atipicos y cambios subitos (umbral >2.5 sigma)
2. **Tendencias preocupantes**: Deterioro consecutivo por 3+ semanas, slopes negativos significativos, diferenciando metricas positivas vs negativas
3. **Benchmarking**: Comparacion entre paises, Wealthy vs Non-Wealthy, y por nivel de priorizacion (High Priority, Prioritized, Not Prioritized)
4. **Correlaciones**: Matriz de correlacion entre las 13 metricas y con volumen de ordenes (correlacion mas fuerte detectada: MLTV Top Verticals Adoption <-> Turbo Adoption, r=0.788)
5. **Oportunidades**: Zonas prioritarias bajo rendimiento, gaps de adopcion, momentum positivo (WoW >5%)
6. **Recomendaciones accionables**: Top 5-7 acciones priorizadas por impacto y urgencia

**Salida**: Markdown (descargable), HTML estilizado con branding Rappi

**Volumenes detectados**: ~30 anomalias, ~25 tendencias preocupantes, ~39 benchmarks, ~20 correlaciones, ~30 oportunidades

## Stack Tecnologico

| Componente | Tecnologia | Justificacion |
|-----------|-----------|---------------|
| **LLM** | GPT-4o (OpenAI) | Alta capacidad de razonamiento, function calling nativo, buen manejo de espanol, velocidad de respuesta |
| **Backend** | Python 3.12 + FastAPI | Ecosistema de datos maduro (Pandas/NumPy), async nativo, validacion con Pydantic, docs automaticos |
| **Frontend** | React 19 | Componentes reutilizables, renderizado markdown nativo, ecosystem robusto |
| **Datos** | Pandas + NumPy | Transformaciones eficientes sobre ~13K filas, analisis estadistico built-in (z-score, correlacion, regresion lineal) |
| **Integracion LLM** | OpenAI SDK + Function Calling | Permite al LLM ejecutar 2 herramientas de analisis con parametros dinamicos sobre datos reales |

### Decisiones de Diseno

- **Function Calling vs RAG**: Se eligio Function Calling porque permite al LLM ejecutar queries dinamicas y calculos precisos sobre los datos reales. RAG con embeddings pierde precision numerica y no permite calculos en tiempo real (promedios, tendencias, correlaciones).
- **Dos herramientas separadas**: `analyze_data` para queries estandar (filtrado, ranking, tendencia) y `cross_metric_analysis` para analisis multivariable que requiere cruzar dos metricas o calcular crecimiento de ordenes. Esto simplifica el schema de cada tool y mejora la precision del LLM al elegir parametros.
- **GPT-4o**: Mejor balance costo/velocidad/calidad para queries interactivas. Respuestas en ~3-8 segundos.
- **Pandas en backend (sin DB)**: Los datos caben en memoria (~12K rows de metricas + ~1.2K de ordenes). Pandas es optimo para transformaciones analiticas sin overhead de conexion a base de datos.
- **FastAPI**: Soporte nativo async, validacion con Pydantic, documentacion automatica OpenAPI en `/docs`.
- **Sanitizacion de NaN**: Los valores NaN de NumPy/Pandas se limpian recursivamente antes de serializar a JSON para evitar errores en la API REST.

## Instalacion y Ejecucion

### Prerrequisitos

- Python 3.11+
- Node.js 18+
- API Key de OpenAI (con acceso a GPT-4o)

### 1. Backend

```bash
cd rappi-insights/backend
pip install -r requirements.txt

# Configurar API key
cp .env.example .env
# Editar .env y agregar tu OPENAI_API_KEY:
# OPENAI_API_KEY=sk-proj-xxxxx...

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
2. En el **Bot Conversacional**, haz clic en cualquiera de las 8 preguntas sugeridas
3. En **Reporte Ejecutivo**, haz clic en "Generar Reporte" (toma ~30-60 segundos)

## Estructura del Proyecto

```
rappi-insights/
├── backend/
│   ├── main.py              # FastAPI app, 8 endpoints REST, CORS, lazy init
│   ├── data_loader.py       # Carga Excel, transformaciones, contexto LLM
│   ├── chatbot.py           # Bot con GPT-4o + 2 Tools (analyze_data, cross_metric_analysis)
│   ├── insights_engine.py   # Motor de insights: anomalias, tendencias, benchmarks, correlaciones
│   ├── requirements.txt     # Dependencias Python
│   ├── .env.example         # Template de configuracion
│   └── .env                 # API key OpenAI (no versionado)
├── frontend/
│   ├── public/
│   │   └── index.html
│   ├── src/
│   │   ├── index.js         # Entry point React
│   │   ├── index.css        # Variables CSS globales (colores Rappi)
│   │   ├── App.js           # Componente principal con navegacion
│   │   ├── App.css          # Layout principal (sidebar + content)
│   │   └── components/
│   │       ├── Sidebar.js/css    # Navegacion lateral con branding
│   │       ├── ChatView.js/css   # Interfaz chatbot (mensajes, sugerencias, typing)
│   │       └── ReportView.js/css # Visor de reportes (generacion, descarga MD, ver HTML)
│   └── package.json
├── data/
│   └── rappi_data.xlsx      # Datos operacionales (RAW_INPUT_METRICS + RAW_ORDERS)
└── README.md
```

## API Endpoints

| Metodo | Endpoint | Descripcion |
|--------|----------|-------------|
| GET | `/` | Info basica de la API |
| GET | `/api/health` | Health check y estado de configuracion de API key |
| GET | `/api/data/summary` | Resumen de dimensiones: paises, ciudades, metricas, tipos de zona |
| POST | `/api/chat` | Enviar mensaje al chatbot (body: `{"message": "..."}`) |
| POST | `/api/chat/reset` | Reiniciar conversacion y memoria |
| GET | `/api/chat/suggestions` | Obtener 8 preguntas sugeridas |
| POST | `/api/insights/report` | Generar reporte ejecutivo completo (JSON con markdown + raw insights) |
| GET | `/api/insights/report/html` | Generar reporte como pagina HTML estilizada con branding Rappi |
| POST | `/api/data/query` | Query directo a los datos con filtros (body: dataset, countries, cities, metrics, zone_types) |

## Datos

El sistema trabaja con dos datasets del archivo Excel:

- **RAW_INPUT_METRICS** (12,573 filas): 13 metricas operacionales por pais/ciudad/zona a lo largo de 9 semanas rolling
- **RAW_ORDERS** (1,242 filas): Volumen de ordenes por pais/ciudad/zona, 9 semanas rolling

**Dimensiones:** 9 paises (AR, BR, CL, CO, CR, EC, MX, PE, UY), ~100+ ciudades, ~1000+ zonas, 2 tipos de zona (Wealthy/Non Wealthy), 3 niveles de priorizacion

### Metricas disponibles

| Metrica | Descripcion | Interpretacion |
|---------|-------------|----------------|
| Perfect Orders | % ordenes completadas sin issues | Mayor = mejor |
| % Order Loss | % ordenes perdidas/canceladas | Menor = mejor |
| Gross Profit UE | Ganancia bruta por unidad economica | Mayor = mejor |
| Pro Adoption (Last Week Status) | % usuarios con Rappi Pro | Mayor = mejor |
| Turbo Adoption | % ordenes usando Rappi Turbo (delivery rapido) | Mayor = mejor |
| Lead Penetration | % conversion desde leads | Mayor = mejor |
| Restaurants SST > SS CVR | Conversion search-to-store en restaurantes | Mayor = mejor |
| Retail SST > SS CVR | Conversion search-to-store en retail | Mayor = mejor |
| Restaurants SS > ATC CVR | Conversion store-to-add-to-cart en restaurantes | Mayor = mejor |
| Restaurants Markdowns / GMV | Ratio de descuentos sobre GMV en restaurantes | Depende del contexto |
| % Restaurants Sessions With Optimal Assortment | % sesiones con menu completo | Mayor = mejor |
| MLTV Top Verticals Adoption | Adopcion multi-vertical (lifetime value) | Mayor = mejor |
| Non-Pro PTC > OP | Conversion purchase-to-order (usuarios no Pro) | Mayor = mejor |
| % PRO Users Who Breakeven | % usuarios Pro que recuperan el costo de suscripcion | Mayor = mejor |

## Guia para la Demo

### Presentacion sugerida (35 min)

1. **Contexto y approach (3 min)**: Explicar la arquitectura, por que Function Calling sobre RAG, por que GPT-4o
2. **Demo del bot (10 min)**: Mostrar las 6 preguntas de diferente complejidad:
   - Filtrado: "¿Cuales son las 5 zonas con mayor % Lead Penetration esta semana?"
   - Comparacion: "Compara el Perfect Order entre zonas Wealthy y Non Wealthy en Mexico"
   - Tendencia: "Muestra la evolucion de Gross Profit UE en Chapinero ultimas 8 semanas"
   - Agregacion: "¿Cual es el promedio de Lead Penetration por pais?"
   - Multivariable: "¿Que zonas tienen alto Lead Penetration pero bajo Perfect Order?"
   - Inferencia: "¿Cuales son las zonas que mas crecen en ordenes en las ultimas 5 semanas?"
3. **Insights automaticos (5 min)**: Generar el reporte y mostrar anomalias, tendencias, recomendaciones
4. **Decisiones tecnicas (5 min)**: Function Calling vs RAG, dos tools, sanitizacion NaN, Pandas sin DB
5. **Limitaciones y proximos pasos (2 min)**: Ver seccion abajo
6. **Q&A (10 min)**

## Limitaciones y Proximos Pasos

### Limitaciones actuales
- Datos estaticos (snapshot Excel, no conexion en tiempo real a warehouse)
- Sin autenticacion de usuarios
- Sin persistencia de conversaciones entre sesiones del navegador
- Visualizaciones en texto/markdown (sin graficos interactivos tipo charts)
- El reporte ejecutivo toma ~30-60 segundos en generarse (depende de la API de OpenAI)

### Proximos pasos con mas tiempo
1. **Visualizaciones interactivas**: Integrar Recharts o D3.js para graficos de tendencias, mapas de calor por zona, y scatter plots de correlacion
2. **Conexion a datos en vivo**: API directa al data warehouse de Rappi (Snowflake/BigQuery) con refresh automatico
3. **Alertas proactivas**: Sistema de notificaciones via Slack/email cuando se detecten anomalias criticas (z-score >3)
4. **Multi-usuario**: Autenticacion OAuth y personalizacion por rol (ops, producto, finanzas)
5. **Exportacion a PDF**: Reportes ejecutivos con formato profesional para presentaciones a liderazgo
6. **Cache inteligente**: Redis para cachear analisis frecuentes y reducir latencia y costos de API
7. **Historico de insights**: Tracking de insights a lo largo del tiempo para medir si las recomendaciones tuvieron impacto medible
8. **Streaming de respuestas**: Server-Sent Events para mostrar la respuesta del bot en tiempo real mientras se genera
