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
        <img
          src={image.url}
          alt={image.name}
          className={styles.image}
        />
        <div className={styles.descriptionPanel}>
          <h3 className={styles.imageTitle}>{image.name}</h3>
          <p className={styles.imageDescription}>{image.description}</p>
        </div>
      </div>
    </div>
  );
};

export default ImageModal;
