// ============================================
// Topology 형식 JSON을 FloorPlanUploadResponse로 변환
// APT_FP_OBJ_001046197_topology.json 구조에 맞춤
// ============================================

import type { FloorPlanUploadResponse, RoomInfo, StructureInfo, ObjectInfo } from '../types/floor-plan.types';

// ============================================
// Topology 형식 타입 정의
// ============================================

interface TopologyBboxXYXY {
  xmin: number;
  ymin: number;
  xmax: number;
  ymax: number;
}

// 공간 내 객체 (bbox 없음, class_name과 confidence만)
interface TopologyNodeObject {
  class_name: string;
  confidence: number;
}

// 공간 노드
interface TopologyNode {
  id: string;
  class_id: number;
  class_name: string;
  instance_id: number;
  segmentation?: number[][];
  bbox: [number, number, number, number];  // [x, y, w, h]
  bbox_xyxy: TopologyBboxXYXY;
  area: number;
  area_ratio: number;
  centroid: [number, number];  // [x, y]
  name: string;
  ocr_label: string | null;
  source: string;
  ocr_match_type: string;
  objects: TopologyNodeObject[];
  has_window: boolean;
}

// 문/창문의 연결 공간 정보
interface TouchingSpace {
  space_id: string;
  space_name: string;
  class_name: string;
  overlap: number;
}

// 문 정보
interface TopologyDoor {
  id: string;
  segmentation?: number[][];
  bbox: [number, number, number, number];
  bbox_xyxy: TopologyBboxXYXY;
  area: number;
  centroid: [number, number];
  instance_id: number;
  temp_id: string;
  touching_spaces: TouchingSpace[];
}

// 창문 정보
interface TopologyWindow {
  id: string;
  segmentation?: number[][];
  bbox: [number, number, number, number];
  bbox_xyxy: TopologyBboxXYXY;
  area: number;
  centroid: [number, number];
  instance_id: number;
  touching_spaces: TouchingSpace[];
}

// 엣지 정보
interface TopologyEdge {
  from: string;
  to: string;
  connection_type: string;
  door_id?: string;
}

// 전체 Topology 데이터
export interface TopologyData {
  version: string;
  nodes: TopologyNode[];
  edges: TopologyEdge[];
  uncertain_edges?: TopologyEdge[];
  doors: TopologyDoor[];
  windows: TopologyWindow[];
  summary?: any;
  refined_summary?: any;
  spatial_relations?: any;
  bay_analysis?: any;
}

// ============================================
// 유틸리티 함수
// ============================================

/**
 * Topology JSON인지 확인
 */
export function isTopologyFormat(data: any): data is TopologyData {
  if (!data || !Array.isArray(data.nodes) || data.nodes.length === 0) return false;
  const firstNode = data.nodes[0];
  // nodes에 bbox_xyxy가 있으면 Topology 형식
  return firstNode.bbox_xyxy !== undefined;
}

/**
 * Topology 형식 데이터를 FloorPlanUploadResponse로 변환
 */
export function convertTopologyToFloorPlan(topology: TopologyData, fileName: string): FloorPlanUploadResponse {
  const rooms: RoomInfo[] = [];
  const structures: StructureInfo[] = [];
  const objects: ObjectInfo[] = [];

  let roomIdCounter = 1;
  let structureIdCounter = 1;
  let objectIdCounter = 1;

  // 1. 공간(nodes) 처리
  for (const node of topology.nodes) {
    const bbox = node.bbox_xyxy;
    const bboxArray: [number, number, number, number] = [bbox.xmin, bbox.ymin, bbox.xmax, bbox.ymax];
    const bboxStr = JSON.stringify(bboxArray);
    const centroid = `${node.centroid[0]},${node.centroid[1]}`;

    // segmentation 처리 (ㄱ자 등 복잡한 형태용)
    let segmentationStr: string | undefined;
    if (node.segmentation && node.segmentation.length > 0) {
      segmentationStr = JSON.stringify(node.segmentation[0]);
    }

    rooms.push({
      id: roomIdCounter++,
      spcname: node.class_name || node.name,
      ocrname: node.ocr_label || node.name,
      bbox: bboxStr,
      centroid: centroid,
      area: node.area,
      areapercent: node.area_ratio * 100,
      segmentation: segmentationStr,
    });

    // 공간 내 객체들 (bbox가 없으므로 공간의 bbox 사용)
    if (node.objects && node.objects.length > 0) {
      for (const obj of node.objects) {
        objects.push({
          id: objectIdCounter++,
          name: obj.class_name,
          bbox: bboxStr,  // 공간의 bbox 사용
          centroid: centroid,
        });
      }
    }
  }

  // 2. 문(doors) → structures로 추가
  if (topology.doors) {
    for (const door of topology.doors) {
      const bbox = door.bbox_xyxy;
      const bboxArray: [number, number, number, number] = [bbox.xmin, bbox.ymin, bbox.xmax, bbox.ymax];
      const centroid = `${door.centroid[0]},${door.centroid[1]}`;

      let segmentationStr: string | undefined;
      if (door.segmentation && door.segmentation.length > 0) {
        segmentationStr = JSON.stringify(door.segmentation[0]);
      }

      structures.push({
        id: structureIdCounter++,
        name: '문',
        bbox: JSON.stringify(bboxArray),
        centroid: centroid,
        area: door.area?.toString() ?? '0',
        segmentation: segmentationStr,
      });
    }
  }

  // 3. 창문(windows) → structures로 추가
  if (topology.windows) {
    for (const window of topology.windows) {
      const bbox = window.bbox_xyxy;
      const bboxArray: [number, number, number, number] = [bbox.xmin, bbox.ymin, bbox.xmax, bbox.ymax];
      const centroid = `${window.centroid[0]},${window.centroid[1]}`;

      let segmentationStr: string | undefined;
      if (window.segmentation && window.segmentation.length > 0) {
        segmentationStr = JSON.stringify(window.segmentation[0]);
      }

      structures.push({
        id: structureIdCounter++,
        name: '창문',
        bbox: JSON.stringify(bboxArray),
        centroid: centroid,
        area: window.area?.toString() ?? '0',
        segmentation: segmentationStr,
      });
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
