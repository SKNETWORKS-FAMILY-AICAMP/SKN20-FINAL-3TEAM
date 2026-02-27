import React, { useEffect, useMemo, useState } from 'react';
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
  const [zoomLevel, setZoomLevel] = useState(1);
  const [panPosition, setPanPosition] = useState({ x: 0, y: 0 });
  const [isPanning, setIsPanning] = useState(false);
  const [panStart, setPanStart] = useState({ x: 0, y: 0 });

  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onClose();
    };
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [onClose]);

  // 이미지 변경 시 줌 리셋
  useEffect(() => {
    setZoomLevel(1);
    setPanPosition({ x: 0, y: 0 });
  }, [image.url]);

  const formattedDescription = useMemo(
    () => (image.description ? toMarkdown(image.description) : ''),
    [image.description],
  );

  const handleZoomWheel = (e: React.WheelEvent) => {
    e.preventDefault();
    const delta = e.deltaY > 0 ? -0.1 : 0.1;
    setZoomLevel((prev) => Math.min(Math.max(prev + delta, 0.5), 5));
  };

  const handlePanStart = (e: React.MouseEvent) => {
    if (zoomLevel > 1) {
      setIsPanning(true);
      setPanStart({ x: e.clientX - panPosition.x, y: e.clientY - panPosition.y });
    }
  };

  const handlePanMove = (e: React.MouseEvent) => {
    if (isPanning && zoomLevel > 1) {
      setPanPosition({
        x: e.clientX - panStart.x,
        y: e.clientY - panStart.y,
      });
    }
  };

  const handlePanEnd = () => {
    setIsPanning(false);
  };

  const handleZoomReset = () => {
    setZoomLevel(1);
    setPanPosition({ x: 0, y: 0 });
  };

  return (
    <div className={styles.overlay} onClick={onClose}>
      <button className={styles.closeButton} onClick={onClose}>
        &times;
      </button>
      <div className={styles.modalContent} onClick={(e) => e.stopPropagation()}>
        {/* 왼쪽: 도면 이미지 (확대/축소/패닝) */}
        <div
          className={styles.imageSection}
          onWheel={handleZoomWheel}
          onMouseDown={handlePanStart}
          onMouseMove={handlePanMove}
          onMouseUp={handlePanEnd}
          onMouseLeave={handlePanEnd}
          style={{ cursor: zoomLevel > 1 ? (isPanning ? 'grabbing' : 'grab') : 'default' }}
        >
          <img
            src={image.url}
            alt={image.name}
            className={styles.image}
            style={{
              transform: `scale(${zoomLevel}) translate(${panPosition.x / zoomLevel}px, ${panPosition.y / zoomLevel}px)`,
              transition: isPanning ? 'none' : 'transform 0.1s ease',
            }}
            draggable={false}
          />
          <div className={styles.zoomControls}>
            <button
              className={styles.zoomControlBtn}
              onClick={() => setZoomLevel((prev) => Math.max(prev - 0.25, 0.5))}
            >
              −
            </button>
            <span className={styles.zoomLevelText}>{Math.round(zoomLevel * 100)}%</span>
            <button
              className={styles.zoomControlBtn}
              onClick={() => setZoomLevel((prev) => Math.min(prev + 0.25, 5))}
            >
              +
            </button>
            {zoomLevel !== 1 && (
              <button className={styles.zoomControlBtn} onClick={handleZoomReset}>
                ↺
              </button>
            )}
          </div>
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
