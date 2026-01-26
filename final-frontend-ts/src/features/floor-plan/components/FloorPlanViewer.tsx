// ============================================
// FloorPlanViewer Component
// 도면 이미지 + Bbox Overlay
// ============================================

import React, { useRef, useMemo } from 'react';
import { useImageScale } from '../hooks/useImageScale';
import type { HoverableItem } from '../types';
import styles from './FloorPlanViewer.module.css';

interface FloorPlanViewerProps {
  imageUrl: string | null;
  hoveredItem: HoverableItem | null;
  allItems?: HoverableItem[]; // 모든 아이템 표시 (옵션)
  showAllBboxes?: boolean;    // 모든 bbox 표시 여부
}

// 타입별 색상 정의
const TYPE_COLORS: Record<string, { fill: string; stroke: string }> = {
  room: { fill: 'rgba(59, 130, 246, 0.25)', stroke: '#3B82F6' },      // 파랑
  structure: { fill: 'rgba(249, 115, 22, 0.25)', stroke: '#F97316' }, // 주황
  object: { fill: 'rgba(34, 197, 94, 0.25)', stroke: '#22C55E' },     // 초록
};

const FloorPlanViewer: React.FC<FloorPlanViewerProps> = ({
  imageUrl,
  hoveredItem,
  allItems = [],
  showAllBboxes = false,
}) => {
  const containerRef = useRef<HTMLDivElement>(null);
  const imageRef = useRef<HTMLImageElement>(null);

  const { transformBbox } = useImageScale(containerRef, imageRef);

  // 표시할 bbox 아이템들
  const displayItems = useMemo(() => {
    if (hoveredItem) {
      // hover된 아이템만 표시
      return [hoveredItem];
    }
    if (showAllBboxes) {
      // 모든 아이템 표시
      return allItems;
    }
    return [];
  }, [hoveredItem, allItems, showAllBboxes]);

  // Overlay 렌더링
  const renderOverlay = (item: HoverableItem, isHovered: boolean) => {
    const { x, y, width, height } = transformBbox(item.bbox);
    const colors = TYPE_COLORS[item.type] || TYPE_COLORS.room;

    return (
      <div
        key={`${item.type}-${item.id}`}
        className={`${styles.bboxOverlay} ${isHovered ? styles.hovered : ''}`}
        style={{
          left: x,
          top: y,
          width,
          height,
          backgroundColor: colors.fill,
          borderColor: colors.stroke,
        }}
      >
        <span
          className={styles.bboxLabel}
          style={{ backgroundColor: colors.stroke }}
        >
          {item.name}
        </span>
      </div>
    );
  };

  return (
    <div ref={containerRef} className={styles.container}>
      {imageUrl ? (
        <>
          <img
            ref={imageRef}
            src={imageUrl}
            alt="도면"
            className={styles.image}
          />
          {/* Bbox Overlays */}
          <div className={styles.overlayContainer}>
            {displayItems.map((item) =>
              renderOverlay(item, hoveredItem?.id === item.id && hoveredItem?.type === item.type)
            )}
          </div>
        </>
      ) : (
        <div className={styles.placeholder}>
          <p>도면 이미지를 업로드해주세요</p>
        </div>
      )}
    </div>
  );
};

export default FloorPlanViewer;
