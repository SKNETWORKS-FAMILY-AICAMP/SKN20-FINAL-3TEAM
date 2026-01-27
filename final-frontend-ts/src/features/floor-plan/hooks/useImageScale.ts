// ============================================
// useImageScale Hook
// 이미지 스케일 및 오프셋 계산
// ============================================

import { useState, useEffect, useCallback } from 'react';
import type { RefObject } from 'react';
import type { Bbox } from '../types/floor-plan.types';

interface ImageScale {
  scaleX: number;
  scaleY: number;
  offsetX: number;
  offsetY: number;
  renderedWidth: number;
  renderedHeight: number;
}

interface UseImageScaleReturn {
  scale: ImageScale;
  transformBbox: (bbox: Bbox) => { x: number; y: number; width: number; height: number };
  updateScale: () => void;
}

/**
 * 이미지의 스케일과 오프셋을 계산하는 훅
 * object-fit: contain 일 때 실제 렌더링된 이미지 크기와 위치를 계산
 */
export const useImageScale = (
  containerRef: RefObject<HTMLDivElement | null>,
  imageRef: RefObject<HTMLImageElement | null>
): UseImageScaleReturn => {
  const [scale, setScale] = useState<ImageScale>({
    scaleX: 1,
    scaleY: 1,
    offsetX: 0,
    offsetY: 0,
    renderedWidth: 0,
    renderedHeight: 0,
  });

  const updateScale = useCallback(() => {
    const container = containerRef.current;
    const image = imageRef.current;

    if (!container || !image || !image.naturalWidth || !image.naturalHeight) {
      return;
    }

    const containerWidth = container.clientWidth;
    const containerHeight = container.clientHeight;
    const naturalWidth = image.naturalWidth;
    const naturalHeight = image.naturalHeight;

    // object-fit: contain 비율 계산
    const containerRatio = containerWidth / containerHeight;
    const imageRatio = naturalWidth / naturalHeight;

    let renderedWidth: number;
    let renderedHeight: number;

    if (imageRatio > containerRatio) {
      // 이미지가 더 넓음 → 너비 기준
      renderedWidth = containerWidth;
      renderedHeight = containerWidth / imageRatio;
    } else {
      // 이미지가 더 높음 → 높이 기준
      renderedHeight = containerHeight;
      renderedWidth = containerHeight * imageRatio;
    }

    // 중앙 정렬 오프셋
    const offsetX = (containerWidth - renderedWidth) / 2;
    const offsetY = (containerHeight - renderedHeight) / 2;

    // 스케일 계산
    const scaleX = renderedWidth / naturalWidth;
    const scaleY = renderedHeight / naturalHeight;

    setScale({
      scaleX,
      scaleY,
      offsetX,
      offsetY,
      renderedWidth,
      renderedHeight,
    });
  }, [containerRef, imageRef]);

  // 이미지 로드 및 리사이즈 시 스케일 업데이트
  useEffect(() => {
    const image = imageRef.current;
    const container = containerRef.current;

    if (!image || !container) return;

    // 이미지 로드 완료 시
    const handleLoad = () => updateScale();
    image.addEventListener('load', handleLoad);

    // 리사이즈 감지
    const resizeObserver = new ResizeObserver(() => updateScale());
    resizeObserver.observe(container);

    // 초기 계산 (이미지가 이미 로드된 경우)
    if (image.complete) {
      updateScale();
    }

    return () => {
      image.removeEventListener('load', handleLoad);
      resizeObserver.disconnect();
    };
  }, [containerRef, imageRef, updateScale]);

  // bbox를 화면 좌표로 변환
  const transformBbox = useCallback(
    (bbox: Bbox): { x: number; y: number; width: number; height: number } => {
      const [x1, y1, x2, y2] = bbox;

      return {
        x: x1 * scale.scaleX + scale.offsetX,
        y: y1 * scale.scaleY + scale.offsetY,
        width: (x2 - x1) * scale.scaleX,
        height: (y2 - y1) * scale.scaleY,
      };
    },
    [scale]
  );

  return { scale, transformBbox, updateScale };
};

export default useImageScale;
