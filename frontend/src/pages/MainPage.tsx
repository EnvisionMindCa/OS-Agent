import React from 'react';
import Header from '../components/Header';
import ChatWindow from '../components/ChatWindow';
import VMStreamViewer from '../components/VMStreamViewer';
import '../styles/MainPage.css'; // We'll create this

const MainPage: React.FC = () => {
  return (
    <div className="main-page-layout">
      <Header />
      <main className="content-area">
        <div className="panel chat-panel">
          <ChatWindow />
        </div>
        <div className="panel vm-panel">
          <VMStreamViewer />
        </div>
      </main>
    </div>
  );
};

export default MainPage;
