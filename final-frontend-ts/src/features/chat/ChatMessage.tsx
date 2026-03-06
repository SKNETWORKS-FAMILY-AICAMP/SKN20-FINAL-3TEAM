import React, { useState } from 'react';
import ReactMarkdown from 'react-markdown';
import remarkBreaks from 'remark-breaks';
import { FiUser, FiExternalLink } from 'react-icons/fi';
import botIcon from '/bot.svg';
import { useTheme } from '@/shared/contexts/ThemeContext';
import ImageModal from './ImageModal';
import type { ChatMessageProps, ChatImage } from './types/chat.types';
import styles from './ChatMessage.module.css';

const ChatMessage: React.FC<ChatMessageProps> = ({ message }) => {
  const { colors } = useTheme();
  const isUser = message.role === 'user';
  const [selectedImage, setSelectedImage] = useState<ChatImage | null>(null);
  const [failedImages, setFailedImages] = useState<Set<number>>(new Set());

  const handleImageError = (idx: number) => {
    setFailedImages(prev => new Set(prev).add(idx));
  };

  return (
    <div className={styles.container}>
      <div
        className={styles.avatar}
        style={{ backgroundColor: isUser ? colors.primary : '#82cded' }}
      >
        {isUser ? <FiUser size={18} color="#fff" /> : <img src={botIcon} alt="bot" style={{ width: 20, height: 20, objectFit: 'contain' }} />}
      </div>

      <div className={styles.content}>
        <div
          className={`${styles.bubble} ${isUser ? styles.bubbleUser : ''}`}
          style={{
            backgroundColor: isUser ? '#FFFFFF' : colors.chatBg,
            color: colors.textPrimary,
          }}
        >
          {isUser ? (
            message.content
          ) : (
            <ReactMarkdown
              remarkPlugins={[remarkBreaks]}
              components={{
                h2: ({ children }) => <h2 className={styles.mdH2}>{children}</h2>,
                h3: ({ children }) => <h3 className={styles.mdH3}>{children}</h3>,
                p: ({ children }) => <p className={styles.mdP}>{children}</p>,
                strong: ({ children }) => <strong className={styles.mdStrong}>{children}</strong>,
                ul: ({ children }) => <ul className={styles.mdUl}>{children}</ul>,
                ol: ({ children }) => <ol className={styles.mdOl}>{children}</ol>,
                li: ({ children }) => (
                  <li className={styles.mdLi}>
                    {React.Children.map(children, child =>
                      React.isValidElement<{ children?: React.ReactNode }>(child) && child.type === 'p'
                        ? child.props.children
                        : child
                    )}
                  </li>
                ),
                a: ({ href, children }) => {
                  let domain = '';
                  try {
                    domain = new URL(href || '').hostname.replace('www.', '');
                  } catch { /* ignore */ }
                  return (
                    <a href={href} target="_blank" rel="noopener noreferrer" className={styles.linkCard}>
                      <span className={styles.linkInfo}>
                        <span className={styles.linkTitle}>{children}</span>
                        <span className={styles.linkDomain}>{domain}</span>
                      </span>
                      <FiExternalLink size={14} className={styles.linkIcon} />
                    </a>
                  );
                },
              }}
            >
              {message.content}
            </ReactMarkdown>
          )}
          {message.images && message.images.length > 0 && (
            <div className={styles.imageGrid}>
              {message.images.map((img, idx) =>
                isUser ? (
                  /* 유저 업로드 이미지: 클릭/그림자 없이 이미지만 표시 */
                  <div key={idx} className={styles.uploadedImageWrap}>
                    <img
                      src={img.url}
                      alt={img.name}
                      className={styles.uploadedImage}
                    />
                  </div>
                ) : (
                  /* AI 응답 도면: 클릭 가능한 썸네일 카드 */
                  <div
                    key={idx}
                    className={styles.thumbnailCard}
                    onClick={() => !failedImages.has(idx) && setSelectedImage(img)}
                    style={{ cursor: failedImages.has(idx) ? 'default' : 'pointer' }}
                  >
                    {failedImages.has(idx) ? (
                      <div className={styles.deletedImagePlaceholder}>
                        <span>🗑️</span>
                        <span>이미지가 삭제되었습니다</span>
                      </div>
                    ) : (
                      <img
                        src={img.url}
                        alt={img.name}
                        className={styles.thumbnail}
                        onError={() => handleImageError(idx)}
                      />
                    )}
                    <span className={styles.thumbnailLabel}>{img.name}</span>
                  </div>
                )
              )}
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
