// ============================================
// Topology 형식 JSON을 FloorPlanUploadResponse로 변환
// ============================================

import type { FloorPlanUploadResponse, RoomInfo, StructureInfo, ObjectInfo } from '../types/floor-plan.types';

// Topology 형식 타입 정의
interface TopologyBbox {
  xmin: number;
  ymin: number;
  xmax: number;
  ymax: number;
}

interface TopologyObject {
  class_name: string;
  confidence: number;
  bbox: TopologyBbox;
}

interface TopologyNode {
  id: string;
  name: string;
  class_id: number;
  class_name: string;
  source: string;
  area_ratio: number;
  pixel_count: number;
  bbox: TopologyBbox;
  centroid: { x: number; y: number };
  ocr_label?: string;
  objects?: TopologyObject[];
  has_window?: boolean;
}

interface TopologyEdge {
  from: string;
  to: string;
  connection_type: string;
}

export interface TopologyData {
  image_name: string;
  timestamp: string;
  version: string;
  nodes: TopologyNode[];
  edges?: TopologyEdge[];
  spatial_relationships?: any;
  bay_analysis?: any;
}

/**
 * Topology JSON인지 확인
 */
export function isTopologyFormat(data: any): data is TopologyData {
  return data && Array.isArray(data.nodes) && data.nodes.length > 0 && data.nodes[0].bbox?.xmin !== undefined;
}

/**
 * Topology 형식 데이터를 FloorPlanUploadResponse로 변환
 */
export function convertTopologyToFloorPlan(topology: TopologyData, fileName: string): FloorPlanUploadResponse {
  const rooms: RoomInfo[] = [];
  const structures: StructureInfo[] = [];
  const objects: ObjectInfo[] = [];

  let roomIdCounter = 1;
  let objectIdCounter = 1;

  for (const node of topology.nodes) {
    // bbox 변환: {xmin, ymin, xmax, ymax} → [x1, y1, x2, y2]
    const bboxArray = [node.bbox.xmin, node.bbox.ymin, node.bbox.xmax, node.bbox.ymax];
    const bboxStr = JSON.stringify(bboxArray);

    // 중심점
    const centroid = `${node.centroid.x},${node.centroid.y}`;

    // 면적 계산 (픽셀 수 또는 bbox 기반)
    const width = node.bbox.xmax - node.bbox.xmin;
    const height = node.bbox.ymax - node.bbox.ymin;
    const area = node.pixel_count || (width * height);

    // 공간을 room으로 추가
    rooms.push({
      id: roomIdCounter++,
      spcname: node.class_name || node.name,
      ocrname: node.ocr_label || node.name,
      bbox: bboxStr,
      centroid: centroid,
      area: area,
      areapercent: node.area_ratio ? node.area_ratio * 100 : 0,
    });

    // 공간 내 객체들 추가
    if (node.objects && node.objects.length > 0) {
      for (const obj of node.objects) {
        const objBboxArray = [obj.bbox.xmin, obj.bbox.ymin, obj.bbox.xmax, obj.bbox.ymax];
        const objCentroidX = (obj.bbox.xmin + obj.bbox.xmax) / 2;
        const objCentroidY = (obj.bbox.ymin + obj.bbox.ymax) / 2;

        objects.push({
          id: objectIdCounter++,
          name: obj.class_name,
          bbox: JSON.stringify(objBboxArray),
          centroid: `${objCentroidX.toFixed(1)},${objCentroidY.toFixed(1)}`,
        });
      }
    }
  }

  // 총 면적 계산
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
