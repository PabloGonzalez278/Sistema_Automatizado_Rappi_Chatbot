import React, { useState } from 'react';
import Sidebar from './components/Sidebar';
import ChatView from './components/ChatView';
import ReportView from './components/ReportView';
import './App.css';

function App() {
  const [activeView, setActiveView] = useState('chat');

  return (
    <div className="app">
      <Sidebar activeView={activeView} setActiveView={setActiveView} />
      <main className="main-content">
        {activeView === 'chat' && <ChatView />}
        {activeView === 'report' && <ReportView />}
      </main>
    </div>
  );
}

export default App;
