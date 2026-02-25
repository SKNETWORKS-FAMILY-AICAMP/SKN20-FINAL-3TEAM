import React, { useEffect, useMemo } from 'react';
import ReactMarkdown from 'react-markdown';
import type { ChatImage } from './types/chat.types';
import styles from './ImageModal.module.css';

interface ImageModalProps {
  image: ChatImage;
  onClose: () => void;
}

/**
 * 백엔드 답변 텍스트를 마크다운으로 변환
 * - ■ → 빈 줄 + 볼드 (섹션 헤더)
 * - • → 마크다운 리스트 아이템 (- )
 * - [공간명] → 빈 줄 + 볼드 (공간 분석 항목)
 */
const toMarkdown = (text: string): string => {
  let result = text;
  // ■ 앞에 빈 줄 삽입 (마크다운 단락 구분)
  result = result.replace(/ ?■/g, '\n\n■');
  // • → 마크다운 리스트 아이템
  result = result.replace(/ ?•/g, '\n-');
  // [공간명] 앞에 빈 줄 삽입 (단, [도면 #N] 마커 제외)
  result = result.replace(/ ?\[(?!도면\s*#)/g, '\n\n[');
  return result.trim();
};

const ImageModal: React.FC<ImageModalProps> = ({ image, onClose }) => {
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onClose();
    };
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [onClose]);

  const formattedDescription = useMemo(
    () => (image.description ? toMarkdown(image.description) : ''),
    [image.description],
  );

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
            {formattedDescription ? (
              <div className={styles.imageDescription}>
                <ReactMarkdown>{formattedDescription}</ReactMarkdown>
              </div>
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
