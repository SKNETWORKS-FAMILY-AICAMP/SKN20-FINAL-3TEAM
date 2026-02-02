// ============================================
// Topology 형식 JSON을 FloorPlanUploadResponse로 변환
// 새로운 topology.json 구조에 맞춤 (2024년 버전)
// ============================================

import type { FloorPlanUploadResponse, RoomInfo, StructureInfo, ObjectInfo } from '../types/floor-plan.types';

// ============================================
// 새로운 Topology 형식 타입 정의
// ============================================

interface ImageInfo {
  file_name: string;
  width: number;
  height: number;
}

// 공간 내 객체 (개별 bbox 포함)
interface ContainedObject {
  object_id: string;
  category_id: number;
  category_name: string;
  bbox: [number, number, number, number]; // [x, y, width, height]
}

// 공간 내 구조물
interface ContainedStructure {
  structure_id: string;
  type: string;
  bbox: [number, number, number, number]; // [x, y, width, height]
}

// 공간이 포함하는 요소들
interface NodeContains {
  objects: ContainedObject[];
  ocr_labels: string[];
  structures: {
    doors: ContainedStructure[];
    windows: ContainedStructure[];
    walls: ContainedStructure[];
  };
}

// 공간 노드
interface TopologyNode {
  node_id: string;
  node_type: string;
  category_id: number;
  category_name: string;
  label: string;
  space_type: string;
  is_outside: boolean;
  bbox: [number, number, number, number]; // [x, y, width, height]
  segmentation: number[][]; // 이중 배열 [[x1, y1, x2, y2, ...]]
  area: number;
  area_ratio: number;
  centroid: [number, number];
  contains: NodeContains;
}

// 엣지 정보
interface TopologyEdge {
  edge_id: string;
  source_node: string;
  target_node: string;
  connection_type: string;
  connection_id: string | null;
}

// 통계 정보
interface TopologyStatistics {
  total_image_area: number;
  total_space_area: number;
  total_inside_area: number;
  space_count: number;
  inside_space_count: number;
  room_count: number;
  bathroom_count: number;
  balcony_count: number;
  bay_count: number;
  space_type_count: Record<string, number>;
  structure_type: string;
  balcony_ratio: number;
  windowless_ratio: number;
}

// 전체 Topology 데이터
export interface TopologyData {
  image_info: ImageInfo;
  nodes: TopologyNode[];
  edges: TopologyEdge[];
  statistics: TopologyStatistics;
}

// ============================================
// 유틸리티 함수
// ============================================

/**
 * [x, y, width, height] → [x1, y1, x2, y2] 변환
 */
function convertBboxXYWH_to_XYXY(bbox: [number, number, number, number]): [number, number, number, number] {
  const [x, y, w, h] = bbox;
  return [x, y, x + w, y + h];
}

/**
 * Topology JSON인지 확인 (새로운 형식)
 */
export function isTopologyFormat(data: any): data is TopologyData {
  if (!data) return false;

  // 새로운 형식: image_info와 nodes가 있고, nodes[0]에 node_id가 있음
  if (data.image_info && Array.isArray(data.nodes) && data.nodes.length > 0) {
    const firstNode = data.nodes[0];
    return firstNode.node_id !== undefined && firstNode.contains !== undefined;
  }

  // 이전 형식 호환: bbox_xyxy가 있으면 이전 Topology
  if (Array.isArray(data.nodes) && data.nodes.length > 0) {
    const firstNode = data.nodes[0];
    return firstNode.bbox_xyxy !== undefined;
  }

  return false;
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

  // 구조물 중복 방지용 Set (structure_id 기준)
  const addedStructureIds = new Set<string>();

  // 1. 공간(nodes) 처리
  for (const node of topology.nodes) {
    // bbox 변환: [x, y, w, h] → [x1, y1, x2, y2]
    const bboxXYXY = convertBboxXYWH_to_XYXY(node.bbox);
    const bboxStr = JSON.stringify(bboxXYXY);
    const centroid = `${node.centroid[0]},${node.centroid[1]}`;

    // segmentation 처리 (이중 배열에서 첫 번째 배열 사용)
    let segmentationStr: string | undefined;
    if (node.segmentation && node.segmentation.length > 0) {
      segmentationStr = JSON.stringify(node.segmentation[0]);
    }

    // 공간 이름 결정 (label 우선, 없으면 category_name에서 "공간_" 제거)
    const spaceName = node.label || node.category_name.replace('공간_', '');
    const ocrName = node.contains.ocr_labels?.[0] || spaceName;

    rooms.push({
      id: roomIdCounter++,
      spcname: spaceName,
      ocrname: ocrName,
      bbox: bboxStr,
      centroid: centroid,
      area: node.area,
      areapercent: node.area_ratio * 100, // 0.0225 → 2.25%
      segmentation: segmentationStr,
    });

    // 2. 공간 내 객체(objects) 처리 - 개별 bbox 사용!
    if (node.contains.objects && node.contains.objects.length > 0) {
      for (const obj of node.contains.objects) {
        const objBboxXYXY = convertBboxXYWH_to_XYXY(obj.bbox);
        const objCentroid = `${obj.bbox[0] + obj.bbox[2] / 2},${obj.bbox[1] + obj.bbox[3] / 2}`;

        // 객체 이름에서 "객체_" 제거
        const objName = obj.category_name.replace('객체_', '');

        objects.push({
          id: objectIdCounter++,
          name: objName,
          bbox: JSON.stringify(objBboxXYXY),
          centroid: objCentroid,
        });
      }
    }

    // 3. 공간 내 구조물(doors, windows) 처리
    const { doors, windows } = node.contains.structures;

    // 문 처리
    if (doors && doors.length > 0) {
      for (const door of doors) {
        // 중복 방지
        if (addedStructureIds.has(door.structure_id)) continue;
        addedStructureIds.add(door.structure_id);

        const doorBboxXYXY = convertBboxXYWH_to_XYXY(door.bbox);
        const doorCentroid = `${door.bbox[0] + door.bbox[2] / 2},${door.bbox[1] + door.bbox[3] / 2}`;

        structures.push({
          id: structureIdCounter++,
          name: door.type || '문',
          bbox: JSON.stringify(doorBboxXYXY),
          centroid: doorCentroid,
          area: '0',
        });
      }
    }

    // 창문 처리
    if (windows && windows.length > 0) {
      for (const window of windows) {
        // 중복 방지
        if (addedStructureIds.has(window.structure_id)) continue;
        addedStructureIds.add(window.structure_id);

        const windowBboxXYXY = convertBboxXYWH_to_XYXY(window.bbox);
        const windowCentroid = `${window.bbox[0] + window.bbox[2] / 2},${window.bbox[1] + window.bbox[3] / 2}`;

        structures.push({
          id: structureIdCounter++,
          name: window.type || '창문',
          bbox: JSON.stringify(windowBboxXYXY),
          centroid: windowCentroid,
          area: '0',
        });
      }
    }
  }

  // 통계 정보 활용
  const stats = topology.statistics;

  return {
    floorPlanId: 0,
    name: fileName,
    imageUrl: `/${fileName}`,
    rooms,
    structures,
    objects,
    totalArea: Math.round(stats?.total_space_area || 0),
    roomCount: stats?.space_count || rooms.length,
  };
}
