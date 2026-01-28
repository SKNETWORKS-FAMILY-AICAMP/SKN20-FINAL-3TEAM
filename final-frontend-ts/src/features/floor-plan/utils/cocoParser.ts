// ============================================
// COCO 형식 JSON을 FloorPlanUploadResponse로 변환
// ============================================

import type { FloorPlanUploadResponse, RoomInfo, StructureInfo, ObjectInfo } from '../types/floor-plan.types';

// COCO 형식 타입 정의
interface CocoCategory {
  id: number;
  name: string;
}

interface CocoImage {
  id: number;
  file_name: string;
  width: number;
  height: number;
}

interface CocoAnnotation {
  id: number;
  image_id: number;
  category_id: number;
  bbox: [number, number, number, number]; // [x, y, width, height]
  area: number;
  attributes?: {
    OCR?: string;
    occluded?: boolean;
    rotation?: number;
  };
}

export interface CocoData {
  categories: CocoCategory[];
  images: CocoImage[];
  annotations: CocoAnnotation[];
}

/**
 * COCO 형식 데이터를 FloorPlanUploadResponse로 변환
 */
export function convertCocoToFloorPlan(coco: CocoData, fileName: string): FloorPlanUploadResponse {
  const categoryMap = new Map(coco.categories.map(c => [c.id, c.name]));

  const rooms: RoomInfo[] = [];
  const structures: StructureInfo[] = [];
  const objects: ObjectInfo[] = [];

  let roomIdCounter = 1;
  let structureIdCounter = 1;
  let objectIdCounter = 1;

  for (const ann of coco.annotations) {
    const categoryName = categoryMap.get(ann.category_id) || '';

    // COCO bbox: [x, y, width, height] → 우리 형식: [x1, y1, x2, y2]
    const [x, y, w, h] = ann.bbox;
    const bboxArray = [x, y, x + w, y + h];
    const bboxStr = JSON.stringify(bboxArray);

    // 중심점 계산
    const centroidX = x + w / 2;
    const centroidY = y + h / 2;
    const centroid = `${centroidX.toFixed(1)},${centroidY.toFixed(1)}`;

    if (categoryName.startsWith('공간_') || categoryName === 'OCR') {
      // OCR 카테고리는 공간 이름 텍스트를 담고 있음
      const spcname = categoryName === 'OCR'
        ? (ann.attributes?.OCR || '기타')
        : categoryName.replace('공간_', '');

      rooms.push({
        id: roomIdCounter++,
        spcname: spcname,
        ocrname: ann.attributes?.OCR || spcname,
        bbox: bboxStr,
        centroid: centroid,
        area: ann.area,
        areapercent: 0, // 추후 계산 가능
      });
    } else if (categoryName.startsWith('구조_')) {
      structures.push({
        id: structureIdCounter++,
        name: categoryName.replace('구조_', ''),
        bbox: bboxStr,
        centroid: centroid,
        area: ann.area.toString(),
      });
    } else if (categoryName.startsWith('객체_')) {
      objects.push({
        id: objectIdCounter++,
        name: categoryName.replace('객체_', ''),
        bbox: bboxStr,
        centroid: centroid,
      });
    }
  }

  // 총 면적 계산 (공간들의 면적 합)
  const totalArea = rooms.reduce((sum, room) => sum + (room.area || 0), 0);

  return {
    floorPlanId: 0,
    name: fileName,
    imageUrl: `/${fileName}`,
    rooms,
    structures,
    objects,
    totalArea: Math.round(totalArea),
    roomCount: rooms.length,
  };
}
