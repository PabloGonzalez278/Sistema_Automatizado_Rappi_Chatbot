import React, { useState } from 'react';
import ReactMarkdown from 'react-markdown';
import { FiFileText, FiDownload, FiRefreshCw, FiExternalLink } from 'react-icons/fi';
import axios from 'axios';
import './ReportView.css';

const API_BASE = process.env.REACT_APP_API_URL || 'http://localhost:8000';

function ReportView() {
  const [report, setReport] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  const generateReport = async () => {
    setLoading(true);
    setError(null);
    try {
      const response = await axios.post(`${API_BASE}/api/insights/report`);
      setReport(response.data);
    } catch (err) {
      setError(err.response?.data?.detail || err.message || 'Error al generar el reporte');
    } finally {
      setLoading(false);
    }
  };

  const downloadMarkdown = () => {
    if (!report) return;
    const blob = new Blob([report.report_markdown], { type: 'text/markdown' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `rappi-reporte-ejecutivo-${new Date().toISOString().slice(0, 10)}.md`;
    a.click();
    URL.revokeObjectURL(url);
  };

  const openHtmlReport = () => {
    window.open(`${API_BASE}/api/insights/report/html`, '_blank');
  };

  return (
    <div className="report-view">
      <header className="report-header">
        <div>
          <h2>Reporte Ejecutivo de Insights</h2>
          <p className="header-subtitle">Analisis automatico con deteccion de anomalias, tendencias y oportunidades</p>
        </div>
        <div className="report-actions">
          {report && (
            <>
              <button className="action-btn" onClick={downloadMarkdown}>
                <FiDownload /> Descargar MD
              </button>
              <button className="action-btn" onClick={openHtmlReport}>
                <FiExternalLink /> Ver HTML
              </button>
            </>
          )}
          <button className="generate-btn" onClick={generateReport} disabled={loading}>
            <FiRefreshCw className={loading ? 'spinning' : ''} />
            {loading ? 'Generando...' : report ? 'Regenerar' : 'Generar Reporte'}
          </button>
        </div>
      </header>

      <div className="report-content">
        {!report && !loading && !error && (
          <div className="empty-state">
            <div className="empty-icon"><FiFileText /></div>
            <h3>Genera un Reporte Ejecutivo</h3>
            <p>
              El sistema analizara automaticamente todos los datos operacionales de Rappi
              para identificar insights accionables en las siguientes categorias:
            </p>
            <div className="features-grid">
              <div className="feature-card">
                <h4>Anomalias</h4>
                <p>Deteccion estadistica de valores atipicos y cambios subitos</p>
              </div>
              <div className="feature-card">
                <h4>Tendencias</h4>
                <p>Identificacion de tendencias preocupantes con deterioro consecutivo</p>
              </div>
              <div className="feature-card">
                <h4>Benchmarking</h4>
                <p>Comparacion entre paises, zonas wealthy vs non-wealthy</p>
              </div>
              <div className="feature-card">
                <h4>Correlaciones</h4>
                <p>Relaciones entre metricas que revelan dinamicas operacionales</p>
              </div>
              <div className="feature-card">
                <h4>Oportunidades</h4>
                <p>Zonas con gaps de adopcion y zonas prioritarias bajo rendimiento</p>
              </div>
              <div className="feature-card">
                <h4>Recomendaciones</h4>
                <p>Acciones priorizadas por impacto y urgencia</p>
              </div>
            </div>
            <button className="generate-btn large" onClick={generateReport}>
              <FiFileText /> Generar Reporte Ejecutivo
            </button>
          </div>
        )}

        {loading && (
          <div className="loading-state">
            <div className="loading-spinner"></div>
            <h3>Analizando datos operacionales...</h3>
            <p>Detectando anomalias, tendencias, correlaciones y oportunidades.</p>
            <p className="loading-note">Esto puede tomar 30-60 segundos</p>
          </div>
        )}

        {error && (
          <div className="error-state">
            <h3>Error al generar el reporte</h3>
            <p>{error}</p>
            <p>Verifica que el backend este corriendo y la API key configurada.</p>
            <button className="generate-btn" onClick={generateReport}>Reintentar</button>
          </div>
        )}

        {report && !loading && (
          <div className="report-document">
            <div className="report-meta">
              <span>Generado: {new Date(report.generated_at).toLocaleString('es-ES')}</span>
              <span>{report.raw_insights?.anomalies?.length || 0} anomalias</span>
              <span>{report.raw_insights?.concerning_trends?.length || 0} tendencias</span>
              <span>{report.raw_insights?.opportunities?.length || 0} oportunidades</span>
            </div>
            <div className="markdown-body">
              <ReactMarkdown>{report.report_markdown}</ReactMarkdown>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

export default ReportView;
