import React, { useState } from 'react';
import ReactMarkdown from 'react-markdown';
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
          {isUser ? (
            message.content
          ) : (
            <ReactMarkdown
              components={{
                p: ({ children }) => <p className={styles.mdP}>{children}</p>,
                strong: ({ children }) => <strong className={styles.mdStrong}>{children}</strong>,
                ul: ({ children }) => <ul className={styles.mdUl}>{children}</ul>,
                ol: ({ children }) => <ol className={styles.mdOl}>{children}</ol>,
                li: ({ children }) => <li className={styles.mdLi}>{children}</li>,
                a: ({ href, children }) => (
                  <a href={href} target="_blank" rel="noopener noreferrer" className={styles.mdLink}>
                    {children}
                  </a>
                ),
              }}
            >
              {message.content}
            </ReactMarkdown>
          )}
          {message.images && message.images.length > 0 && (
            <div className={styles.imageGrid}>
              {message.images.map((img, idx) => (
                <div
                  key={idx}
                  className={styles.thumbnailCard}
                  onClick={() => setSelectedImage(img)}
                >
                  <img
                    src={img.url}
                    alt={img.name}
                    className={styles.thumbnail}
                  />
                  <span className={styles.thumbnailLabel}>{img.name}</span>
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
