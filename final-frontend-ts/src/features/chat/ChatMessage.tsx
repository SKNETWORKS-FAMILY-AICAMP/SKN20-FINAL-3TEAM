import React from 'react';
import { FiUser } from 'react-icons/fi';
import { RiRobot2Line } from 'react-icons/ri';
import { useTheme } from '@/shared/contexts/ThemeContext';
import type { ChatMessageProps } from './types/chat.types';
import styles from './ChatMessage.module.css';

const ChatMessage: React.FC<ChatMessageProps> = ({ message }) => {
  const { colors } = useTheme();
  const isUser = message.role === 'user';

  return (
    <div className={styles.container}>
      <div
        className={styles.avatar}
        style={{ backgroundColor: isUser ? colors.primary : colors.secondary }}
      >
        {isUser ? <FiUser size={18} color="#fff" /> : <RiRobot2Line size={18} color="#fff" />}
      </div>

      <div className={styles.content}>
        <div
          className={styles.bubble}
          style={{
            backgroundColor: isUser ? '#FFFFFF' : colors.chatBg,
            color: colors.textPrimary,
          }}
        >
          {message.content}
        </div>
      </div>
    </div>
  );
};

export default ChatMessage;
