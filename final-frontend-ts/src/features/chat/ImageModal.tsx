import React, { useEffect } from 'react';
import type { ChatImage } from './types/chat.types';
import styles from './ImageModal.module.css';

interface ImageModalProps {
  image: ChatImage;
  onClose: () => void;
}

const ImageModal: React.FC<ImageModalProps> = ({ image, onClose }) => {
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onClose();
    };
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [onClose]);

  return (
    <div className={styles.overlay} onClick={onClose}>
      <button className={styles.closeButton} onClick={onClose}>
        &times;
      </button>
      <div className={styles.modalContent} onClick={(e) => e.stopPropagation()}>
        {/* 왼쪽: 도면 이미지 */}
        <div className={styles.imageSection}>
          <img
            src={image.url}
            alt={image.name}
            className={styles.image}
          />
        </div>

        {/* 오른쪽: 설명 카드 */}
        <div className={styles.descriptionPanel}>
          <div className={styles.descriptionHeader}>
            <h3 className={styles.imageTitle}>{image.name}</h3>
          </div>
          <div className={styles.descriptionBody}>
            {image.description ? (
              <p className={styles.imageDescription}>{image.description}</p>
            ) : (
              <p className={styles.noDescription}>상세 설명이 없습니다.</p>
            )}
          </div>
        </div>
      </div>
    </div>
  );
};

export default ImageModal;
