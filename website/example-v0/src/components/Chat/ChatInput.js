import React, { useState, useCallback } from 'react';
import PropTypes from 'prop-types';
import styles from './Chat.module.css';

function ChatInput({ onSendMessage, placeholder, disabled }) {
  const [message, setMessage] = useState('');

  const handleSend = useCallback(() => {
    const trimmedMessage = message.trim();
    if (trimmedMessage && !disabled) {
      onSendMessage(trimmedMessage);
      setMessage('');
    }
  }, [message, onSendMessage, disabled]);

  const handleKeyDown = useCallback((e) => {
    if (e.key === 'Enter' && !e.shiftKey && !disabled) {
      e.preventDefault();
      handleSend();
    }
  }, [handleSend, disabled]);

  const handleChange = useCallback((e) => {
    setMessage(e.target.value);
  }, []);

  const isMessageValid = message.trim().length > 0 && !disabled;

  return (
    <>
      <div className={styles.inputWrapper}>
        <textarea
          className={`${styles.textArea} ${disabled ? styles.disabled : ''}`}
          value={message}
          onChange={handleChange}
          onKeyDown={handleKeyDown}
          placeholder={disabled ? 'Please wait...' : placeholder}
          rows={1}
          aria-label="Chat input"
          disabled={disabled}
        />
        <button
          className={`${styles.sendButton} ${isMessageValid ? styles.active : styles.inactive}`}
          onClick={handleSend}
          disabled={!isMessageValid}
          aria-label="Send message"
          type="button"
        >
          <svg 
            width="18" 
            height="18" 
            viewBox="0 0 24 24" 
            fill="none" 
            stroke="currentColor" 
            strokeWidth="2"
          >
            <path d="M22 2L11 13M22 2l-7 20-4-9-9-4 20-7z"/>
          </svg>
        </button>
      </div>
      <div className={styles.inputFooter}>
        {/* Add your footer content here */}
      </div>
    </>
  );
}

ChatInput.propTypes = {
  onSendMessage: PropTypes.func.isRequired,
  placeholder: PropTypes.string,
  disabled: PropTypes.bool
};

ChatInput.defaultProps = {
  placeholder: 'Message ABI...',
  disabled: false
};

export default ChatInput;