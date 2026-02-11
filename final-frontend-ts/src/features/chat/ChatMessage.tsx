import React, { useState } from 'react';
import { FiUser } from 'react-icons/fi';
import { RiRobot2Line } from 'react-icons/ri';
import { useTheme } from '@/shared/contexts/ThemeContext';
import ImageModal from './ImageModal';
import type { ChatMessageProps, ChatImage } from './types/chat.types';
import styles from './ChatMessage.module.css';

const ChatMessage: React.FC<ChatMessageProps> = ({ message }) => {
  const { colors } = useTheme();
  const isUser = message.role === 'user';
  const [selectedImage, setSelectedImage] = useState<ChatImage | null>(null);

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
          {message.images && message.images.length > 0 && (
            <div className={styles.imageGrid}>
              {message.images.map((img, idx) => (
                <div key={idx} className={styles.thumbnailWrapper}>
                  <img
                    src={img.url}
                    alt={img.name}
                    className={styles.thumbnail}
                    onClick={() => setSelectedImage(img)}
                  />
                  <span className={styles.thumbnailName}>{img.name}</span>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>
      {selectedImage && (
        <ImageModal image={selectedImage} onClose={() => setSelectedImage(null)} />
      )}
    </div>
  );
};

export default ChatMessage;
