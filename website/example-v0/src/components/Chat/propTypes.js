import PropTypes from 'prop-types';

export const MessagePropType = PropTypes.shape({
  id: PropTypes.string.isRequired,
  content: PropTypes.string.isRequired,
  role: PropTypes.oneOf(['user', 'assistant']).isRequired,
  timestamp: PropTypes.instanceOf(Date).isRequired,
});

export const ChatInputPropTypes = {
  onSendMessage: PropTypes.func.isRequired,
};

export const MessageListPropTypes = {
  messages: PropTypes.arrayOf(MessagePropType).isRequired,
};

export const MessagePropTypes = {
  message: MessagePropType.isRequired,
}; 