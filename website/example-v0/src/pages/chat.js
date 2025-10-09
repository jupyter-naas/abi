import React, { useEffect } from 'react';
import Layout from '@theme/Layout';
import ChatContainer from '../components/Chat/ChatContainer';
import styles from '../components/Chat/Chat.module.css';

function ChatPage() {
  console.log('ChatPage is rendering');

  useEffect(() => {
    console.log('ChatPage mounted');
  }, []);

  return (
    <Layout
      title="Chat"
      description="Chat interface"
      wrapperClassName={styles.pageWrapper}
      noFooter
    >
      <main className={styles.container}>
        <h1 style={{ textAlign: 'center', marginTop: '2rem' }}>Chat Page Test</h1>
        <ChatContainer />
      </main>
    </Layout>
  );
}

export default ChatPage; 