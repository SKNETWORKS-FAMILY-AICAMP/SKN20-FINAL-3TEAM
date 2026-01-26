// ============================================
// FloorPlan Feature - Type Definitions
// ============================================

// ============================================
// 공통 타입
// ============================================

// Bbox 타입: [x_min, y_min, x_max, y_max]
export type Bbox = [number, number, number, number];

// Hover 가능한 아이템 (JSON Inspector에서 사용)
export interface HoverableItem {
  id: number;
  type: 'room' | 'structure' | 'object';
  name: string;
  bbox: Bbox;
}

// ============================================
// DB 기반 타입 (ERD 참조)
// ============================================

// 방 정보 (room 테이블)
export interface RoomInfo {
  id: number;
  spcname: string;       // 공간 이름 (space name)
  ocrname: string;       // OCR 인식 이름
  bbox: Bbox;            // 바운딩 박스 좌표 [x1, y1, x2, y2]
  centroid: string;      // 중심점 좌표
  area: number;          // 면적
  areapercent: number;   // 면적 비율
  floorplan_id?: number; // FK
}

// 구조물 정보 (strs 테이블 - 벽, 문, 창문 등)
export interface StructureInfo {
  id: number;
  name: string;          // 구조물 이름
  bbox: Bbox;            // 바운딩 박스 좌표 [x1, y1, x2, y2]
  centroid: string;      // 중심점 좌표
  area: string;          // 면적 (VARCHAR)
  room_id?: number;      // FK
}

// 객체 정보 (objs 테이블 - 가구, 설비 등)
export interface ObjectInfo {
  id: number;
  name: string;          // 객체 이름
  bbox: Bbox;            // 바운딩 박스 좌표 [x1, y1, x2, y2]
  centroid: string;      // 중심점 좌표
  room_id?: number;      // FK
}

// 도면 정보 (floor_plans 테이블)
export interface FloorPlan {
  id: number;
  name: string;
  imageUrl: string;
  user_id: number;
  created_at: string;
}

// ============================================
// API Request/Response Types
// ============================================

// 도면 업로드 응답 (분석 결과)
export interface FloorPlanUploadResponse {
  floorPlanId: number;
  name: string;
  imageUrl: string;
  rooms: RoomInfo[];
  structures: StructureInfo[];
  objects: ObjectInfo[];
  totalArea: number;
  roomCount: number;
}

// 도면 저장 요청
export interface FloorPlanSaveRequest {
  data: string; // JSON string
}

// 도면 저장 응답
export interface FloorPlanSaveResponse {
  message: string;
}

// ============================================
// UI State Types
// ============================================

// 분석 상태 타입
export type AnalysisStatus = 'idle' | 'analyzing' | 'completed' | 'error';

// 토폴로지 정보 (시각화용)
export interface TopologyInfo {
  nodes: number;
  edges: number;
  graph_type: string;
}

// 도면 분석 결과 (UI용 - 이전 버전 호환)
export interface FloorPlanAnalysisResult {
  floor_plan_id: string;
  analysis_version: string;
  rooms: RoomInfo[];
  total_area: number;
  room_count: number;
  topology?: TopologyInfo;
}
