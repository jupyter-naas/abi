import React from 'react';
import PropTypes from 'prop-types';
import styles from './Chat.module.css';

function ChatHeader({ onClearChat, children }) {
  return (
    <div className={styles.headerContainer}>
      <div className={styles.header}>
        <div></div>
        <div className={styles.actions}>
          {children}
          <button
            onClick={onClearChat}
            className={styles.clearButton}
            aria-label="Clear chat history"
          >
            <span className={styles.clearText}>Clear History</span>
            <svg
              xmlns="http://www.w3.org/2000/svg"
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              strokeWidth="2"
              strokeLinecap="round"
              strokeLinejoin="round"
            >
              <path d="M3 6h18" />
              <path d="M19 6v14c0 1-1 2-2 2H7c-1 0-2-1-2-2V6" />
              <path d="M8 6V4c0-1 1-2 2-2h4c1 0 2 1 2 2v2" />
            </svg>
          </button>
        </div>
      </div>
    </div>
  );
}

ChatHeader.propTypes = {
  onClearChat: PropTypes.func.isRequired,
  children: PropTypes.node,
};

export default ChatHeader; 