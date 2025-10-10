import React from 'react';
import Layout from '@theme/Layout';
import Chat from '../components/Chat';

export default function ChatPage() {
  return (
    <Layout
      title="Chat"
      description="Chat with ABI - Agentic Brain Infrastructure">
      
      <div style={{ 
        height: 'calc(100vh - var(--ifm-navbar-height))', 
        position: 'relative',
        overflow: 'hidden'
      }}>
        <Chat />
      </div>
    </Layout>
  );
}