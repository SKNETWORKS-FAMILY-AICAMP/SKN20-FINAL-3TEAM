// ============================================
// FloorPlan Feature - Type Definitions
// ============================================

// ============================================
// 공통 타입
// ============================================

// Bbox 타입: UI에서 사용하는 배열 형태
export type Bbox = [number, number, number, number];

// Segmentation 타입: 폴리곤 좌표 배열 [x1, y1, x2, y2, ...]
export type Segmentation = number[];

// Bbox 문자열 파싱 유틸리티
export const parseBbox = (bboxStr: string): Bbox => {
  try {
    return JSON.parse(bboxStr) as Bbox;
  } catch {
    return [0, 0, 0, 0];
  }
};

// Segmentation 문자열 파싱 유틸리티
export const parseSegmentation = (segStr: string): Segmentation | null => {
  try {
    const parsed = JSON.parse(segStr);
    return Array.isArray(parsed) ? parsed : null;
  } catch {
    return null;
  }
};

// Hover 가능한 아이템 (JSON Inspector에서 사용)
export interface HoverableItem {
  id: number;
  type: 'room' | 'structure' | 'object';
  name: string;
  bbox: Bbox;
  segmentation?: Segmentation;  // 폴리곤 좌표 (ㄱ자 등 복잡한 형태용)
  areapercent?: number;         // 면적 비율 (rooms 전용)
}

// 그룹화된 아이템 (같은 이름끼리 묶음)
export interface GroupedHoverableItem {
  name: string;
  type: 'room' | 'structure' | 'object';
  count: number;
  items: HoverableItem[];       // 그룹에 속한 모든 아이템
  totalAreaPercent?: number;    // 합산 비율 (rooms 전용)
}

// ============================================
// DB 기반 타입 (백엔드 엔티티와 일치)
// ============================================

// 구조물 정보 (STR 엔티티 - 벽, 문, 창문 등)
export interface StructureInfo {
  id: number;
  name: string;          // 구조물 이름
  bbox: string;          // 바운딩 박스 좌표 (JSON 문자열)
  centroid: string;      // 중심점 좌표
  area: string;          // 면적 (VARCHAR)
  segmentation?: string; // 폴리곤 좌표 (JSON 문자열)
}

// 객체 정보 (OBJ 엔티티 - 가구, 설비 등)
export interface ObjectInfo {
  id: number;
  name: string;          // 객체 이름
  bbox: string;          // 바운딩 박스 좌표 (JSON 문자열)
  centroid: string;      // 중심점 좌표
}

// 방 정보 (Room 엔티티)
export interface RoomInfo {
  id: number;
  spcname: string;       // 공간 이름 (space name)
  ocrname: string;       // OCR 인식 이름
  bbox: string;          // 바운딩 박스 좌표 (JSON 문자열)
  centroid: string;      // 중심점 좌표
  area: number;          // 면적
  areapercent: number;   // 면적 비율
  segmentation?: string; // 폴리곤 좌표 (JSON 문자열) - ㄱ자 등 복잡한 형태용
  strs?: StructureInfo[];  // 구조물 목록
  objs?: ObjectInfo[];     // 객체 목록
}

// 도면 정보 (floor_plans 테이블)
export interface FloorPlan {
  id: number;
  name: string;
  imageUrl: string;
  user: { id: number; name: string; email: string };
  createdAt: string;
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

  // 백엔드 FloorplanPreviewResponse 필드 (Spring Boot)
  topologyJson?: string;              // topology.json 내용 (JSON 문자열)
  topologyImageUrl?: string;          // 위상 그래프 이미지 URL (data:image/png;base64,...)
  analysisDescription?: string;       // 상세 분석 설명
  embedding?: number[];               // 임베딩 벡터 (1536차원)

  // 13개 분석 지표
  windowlessRatio?: number;           // 무창실 비율
  hasSpecialSpace?: boolean;          // 특수 공간 존재 여부
  bayCount?: number;                  // 베이 개수
  balconyRatio?: number;              // 발코니 비율
  livingRoomRatio?: number;           // 거실 비율
  bathroomRatio?: number;             // 욕실 비율
  kitchenRatio?: number;              // 주방 비율
  roomCount2?: number;                // 방 개수 (roomCount와 구분)
  complianceGrade?: string;           // 법적 준수 등급
  ventilationQuality?: string;        // 환기 품질
  hasEtcSpace?: boolean;              // 기타 공간 존재 여부
  structureType?: string;             // 구조 타입
  bathroomCount?: number;             // 욕실 개수

  // 레거시 필드명 (호환성 유지)
  elementJson?: string | object;      // 분석 JSON 데이터 (= topologyJson)
  topologyImage?: string;             // 위상 그래프 이미지 (= topologyImageUrl)
  eval?: string;                      // AI 평가 내용 (= analysisDescription)
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
