import React from 'react';
import { FiMessageSquare, FiFileText, FiBarChart2 } from 'react-icons/fi';
import './Sidebar.css';

function Sidebar({ activeView, setActiveView }) {
  return (
    <aside className="sidebar">
      <div className="sidebar-header">
        <div className="logo">
          <FiBarChart2 className="logo-icon" />
          <div>
            <h1>Rappi Insights</h1>
            <span className="subtitle">Analisis Inteligente</span>
          </div>
        </div>
      </div>
      <nav className="sidebar-nav">
        <button
          className={`nav-item ${activeView === 'chat' ? 'active' : ''}`}
          onClick={() => setActiveView('chat')}
        >
          <FiMessageSquare />
          <span>Bot Conversacional</span>
        </button>
        <button
          className={`nav-item ${activeView === 'report' ? 'active' : ''}`}
          onClick={() => setActiveView('report')}
        >
          <FiFileText />
          <span>Reporte Ejecutivo</span>
        </button>
      </nav>
      <div className="sidebar-footer">
        <div className="tech-badge">Powered by Claude AI</div>
        <p className="version">v1.0.0</p>
      </div>
    </aside>
  );
}

export default Sidebar;
