import React, { useState, useCallback, useEffect } from 'react';
import ChatHeader from './ChatHeader';
import MessageList from './MessageList';
import ChatInput from './ChatInput';
import ModeSelector from './ModeSelector';
import styles from './Chat.module.css';
import ExecutionEnvironment from '@docusaurus/ExecutionEnvironment';
import { generateResponse } from './services/geminiService';

function ChatContainer() {
  console.log('ChatContainer is rendering');
  
  const [messages, setMessages] = useState(() => {
    if (ExecutionEnvironment.canUseDOM) {
      const savedMessages = localStorage.getItem('chatMessages');
      if (savedMessages) {
        return JSON.parse(savedMessages);
      }
    }
    return [];
  });

  const [mode, setMode] = useState('test'); // Default to test mode
  const [isLoading, setIsLoading] = useState(false);

  const showLoadingAndGreeting = useCallback(() => {
    // Clear existing messages first
    setMessages([{
      id: 'loading',
      content: "...",
      timestamp: new Date().toISOString(),
      role: 'assistant',
    }]);

    setTimeout(() => {
      const greetingMessage = {
        id: 'initial-greeting',
        content: "Hi, I'm Bob, how can I help? If you want to explore what I can do maybe start [here](/docs/solutions/market-intelligence).",
        timestamp: new Date().toISOString(),
        role: 'assistant',
      };
      setMessages([greetingMessage]);
    }, 1500);
  }, []);

  useEffect(() => {
    if (!ExecutionEnvironment.canUseDOM) return;
    
    console.log('ChatContainer mounted');
    if (messages.length === 0) {
      showLoadingAndGreeting();
    }
  }, []); 

  useEffect(() => {
    if (!ExecutionEnvironment.canUseDOM) return;

    console.log('Messages updated:', messages);
    localStorage.setItem('chatMessages', JSON.stringify(messages));
  }, [messages]);

  const handleTestModeResponse = (content) => {
    return new Promise((resolve) => {
      setTimeout(() => {
        resolve('This is a test mode response. The AI is simulated.');
      }, 1000);
    });
  };

  const handleSendMessage = useCallback(async (content) => {
    if (!ExecutionEnvironment.canUseDOM) return;

    console.log('Sending message:', content);
    const newMessage = {
      id: Date.now().toString(),
      content,
      timestamp: new Date().toISOString(),
      role: 'user',
    };
    setMessages(prev => [...prev, newMessage]);
    
    setIsLoading(true);
    try {
      const response = mode === 'test' 
        ? await handleTestModeResponse(content)
        : await generateResponse(content);

      const assistantMessage = {
        id: (Date.now() + 1).toString(),
        content: response,
        timestamp: new Date().toISOString(),
        role: 'assistant',
      };
      setMessages(prev => [...prev, assistantMessage]);
    } catch (error) {
      console.error('Error getting response:', error);
      const errorMessage = {
        id: (Date.now() + 1).toString(),
        content: error.message.includes('API key') 
          ? 'Gemini API key not configured. Please switch to Test Mode or configure your API key.'
          : 'I apologize, but I encountered an error. Please try again.',
        timestamp: new Date().toISOString(),
        role: 'assistant',
      };
      setMessages(prev => [...prev, errorMessage]);
    } finally {
      setIsLoading(false);
    }
  }, [mode]);

  const handleClearChat = useCallback(() => {
    if (!ExecutionEnvironment.canUseDOM) return;

    console.log('Clearing chat');
    showLoadingAndGreeting();
    localStorage.clear();
  }, [showLoadingAndGreeting]);

  const handleReload = useCallback(() => {
    showLoadingAndGreeting();
  }, [showLoadingAndGreeting]);

  const handleModeChange = useCallback((newMode) => {
    setMode(newMode);
    handleClearChat(); // Clear chat when mode changes
  }, [handleClearChat]);

  return (
    <div className={styles.chatWrapper}>
      <div className={styles.container}>
        <ChatHeader onClearChat={handleClearChat} />
        <div className={styles.scrollContainer}>
          <MessageList messages={messages} />
        </div>
        <div className={styles.inputContainer}>
          <ChatInput onSendMessage={handleSendMessage} disabled={isLoading} />
          <div className={styles.buttonGroup}>
            <button 
              onClick={handleReload} 
              className={styles.reloadButton}
              disabled={isLoading}
            >
              Reload Chat
            </button>
            <ModeSelector mode={mode} onModeChange={handleModeChange} />
          </div>
          <p className={styles.disclaimer}>
            AI doesn't replace your judgment. You're accountable for its use.
          </p>
        </div>
      </div>
    </div>
  );
}

export default ChatContainer; 