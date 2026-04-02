import React, { useState, useRef, useEffect } from 'react';
import ReactMarkdown from 'react-markdown';
import { FiSend, FiRefreshCw, FiCpu, FiUser } from 'react-icons/fi';
import axios from 'axios';
import './ChatView.css';

const API_BASE = process.env.REACT_APP_API_URL || 'http://localhost:8000';

const INITIAL_SUGGESTIONS = [
  "¿Cual es el pais con mas ordenes esta semana?",
  "¿Como ha evolucionado Perfect Orders en Colombia?",
  "Compara zonas Wealthy vs Non Wealthy en conversion",
  "¿Cuales son las 5 ciudades con peor % Order Loss?",
  "¿Que correlacion hay entre Pro Adoption y Gross Profit?",
  "Muestra tendencias de Turbo Adoption por pais",
  "Dame un resumen de metricas de restaurantes en Mexico",
  "¿Que zonas priorizadas tienen peor rendimiento?",
];

function ChatView() {
  const [messages, setMessages] = useState([]);
  const [input, setInput] = useState('');
  const [loading, setLoading] = useState(false);
  const [suggestions, setSuggestions] = useState(INITIAL_SUGGESTIONS);
  const messagesEndRef = useRef(null);
  const inputRef = useRef(null);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  const sendMessage = async (text) => {
    const userMessage = text || input.trim();
    if (!userMessage || loading) return;

    setInput('');
    setMessages(prev => [...prev, { role: 'user', content: userMessage }]);
    setLoading(true);

    try {
      const response = await axios.post(`${API_BASE}/api/chat`, {
        message: userMessage,
      });
      setMessages(prev => [...prev, {
        role: 'assistant',
        content: response.data.response,
      }]);
      if (response.data.suggestions?.length) {
        setSuggestions(response.data.suggestions);
      }
    } catch (error) {
      const errMsg = error.response?.data?.detail || error.message || 'Error de conexion';
      setMessages(prev => [...prev, {
        role: 'assistant',
        content: `**Error:** ${errMsg}\n\nAsegurate de que el backend este corriendo en \`${API_BASE}\` y que la API key de Anthropic este configurada.`,
        isError: true,
      }]);
    } finally {
      setLoading(false);
      inputRef.current?.focus();
    }
  };

  const resetChat = async () => {
    try {
      await axios.post(`${API_BASE}/api/chat/reset`);
    } catch { /* ignore */ }
    setMessages([]);
    setSuggestions(INITIAL_SUGGESTIONS);
  };

  const handleKeyDown = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      sendMessage();
    }
  };

  return (
    <div className="chat-view">
      <header className="chat-header">
        <div>
          <h2>Bot Conversacional de Datos</h2>
          <p className="header-subtitle">Pregunta sobre metricas operacionales de Rappi</p>
        </div>
        <button className="reset-btn" onClick={resetChat} title="Nueva conversacion">
          <FiRefreshCw /> Nueva conversacion
        </button>
      </header>

      <div className="chat-messages">
        {messages.length === 0 && (
          <div className="welcome-screen">
            <div className="welcome-icon"><FiCpu /></div>
            <h3>Bienvenido al Asistente de Datos Rappi</h3>
            <p>Haz preguntas sobre metricas operacionales, tendencias, comparaciones y mas. Algunos ejemplos:</p>
            <div className="suggestions-grid">
              {suggestions.map((s, i) => (
                <button key={i} className="suggestion-chip" onClick={() => sendMessage(s)}>
                  {s}
                </button>
              ))}
            </div>
          </div>
        )}

        {messages.map((msg, i) => (
          <div key={i} className={`message ${msg.role} ${msg.isError ? 'error' : ''}`}>
            <div className="message-avatar">
              {msg.role === 'user' ? <FiUser /> : <FiCpu />}
            </div>
            <div className="message-content">
              <ReactMarkdown>{msg.content}</ReactMarkdown>
            </div>
          </div>
        ))}

        {loading && (
          <div className="message assistant">
            <div className="message-avatar"><FiCpu /></div>
            <div className="message-content">
              <div className="typing-indicator">
                <span></span><span></span><span></span>
              </div>
            </div>
          </div>
        )}

        <div ref={messagesEndRef} />
      </div>

      {messages.length > 0 && suggestions.length > 0 && !loading && (
        <div className="follow-up-suggestions">
          {suggestions.slice(0, 3).map((s, i) => (
            <button key={i} className="follow-up-chip" onClick={() => sendMessage(s)}>
              {s}
            </button>
          ))}
        </div>
      )}

      <div className="chat-input-area">
        <div className="input-wrapper">
          <textarea
            ref={inputRef}
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder="Escribe tu pregunta sobre los datos de Rappi..."
            rows={1}
            disabled={loading}
          />
          <button
            className="send-btn"
            onClick={() => sendMessage()}
            disabled={!input.trim() || loading}
          >
            <FiSend />
          </button>
        </div>
        <p className="input-hint">Enter para enviar - 9 paises - 13 metricas - 9 semanas de datos</p>
      </div>
    </div>
  );
}

export default ChatView;
