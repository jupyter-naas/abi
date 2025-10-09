import React, { memo, useEffect } from 'react';
import PropTypes from 'prop-types';
import Link from '@docusaurus/Link';
import styles from './Chat.module.css';

const Message = memo(function Message({ role, content }) {
  const isUser = role === 'user';
  console.log('Message rendering:', { role, content });

  const renderContent = (text) => {
    // Regular expression to match markdown links: [text](url)
    const linkRegex = /\[([^\]]+)\]\(([^)]+)\)/g;
    const parts = [];
    let lastIndex = 0;
    let match;

    while ((match = linkRegex.exec(text)) !== null) {
      // Add text before the link
      if (match.index > lastIndex) {
        parts.push(text.slice(lastIndex, match.index));
      }
      // Add the link component
      parts.push(
        <Link key={match.index} to={match[2]}>
          {match[1]}
        </Link>
      );
      lastIndex = match.index + match[0].length;
    }
    // Add remaining text after last link
    if (lastIndex < text.length) {
      parts.push(text.slice(lastIndex));
    }
    return parts.length > 0 ? parts : text;
  };

  return (
    <div className={`${styles.messageGroup} ${isUser ? styles.user : styles.assistant}`}>
      <div className={styles.messageWrapper}>
        <div className={`${styles.avatar} ${isUser ? styles.user : styles.assistant}`}>
          {isUser ? 'U' : (
            <img 
              src="img/BOB-Avatar.png" 
              alt="Bob Avatar" 
              className={styles.avatarImage}
              onError={(e) => console.error('Image failed to load:', e)}
            />
          )}
        </div>
        <div className={styles.messageContent}>
          {content === '...' ? (
            <div className={styles.typingIndicator}>
              <span>.</span>
              <span>.</span>
              <span>.</span>
            </div>
          ) : (
            renderContent(content)
          )}
        </div>
      </div>
    </div>
  );
});

Message.propTypes = {
  role: PropTypes.oneOf(['user', 'assistant']).isRequired,
  content: PropTypes.string.isRequired
};

function MessageList({ messages }) {
  useEffect(() => {
    console.log('MessageList received messages:', messages);
  }, [messages]);

  return (
    <div className={styles.messageContainer}>
      {messages.map(({ id, role, content }) => {
        console.log('Rendering message:', { id, role, content });
        return (
          <Message 
            key={id} 
            role={role} 
            content={content} 
          />
        );
      })}
    </div>
  );
}

MessageList.propTypes = {
  messages: PropTypes.arrayOf(
    PropTypes.shape({
      id: PropTypes.string.isRequired,
      role: PropTypes.oneOf(['user', 'assistant']).isRequired,
      content: PropTypes.string.isRequired,
      timestamp: PropTypes.string
    })
  ).isRequired
};

export default memo(MessageList); 