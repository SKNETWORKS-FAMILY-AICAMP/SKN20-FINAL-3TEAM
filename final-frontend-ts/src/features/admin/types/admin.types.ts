// ============================================
// Admin Feature - Type Definitions
// ============================================

// ============================================
// FloorPlan 관련 타입
// ============================================

export interface AdminFloorPlan {
  id: number;
  name: string;
  imageUrl: string;
  user: {
    id: number;
    email: string;
    name: string;
    role: string;
  };
  createdAt: string;
  roomCount?: number;
  rooms?: AdminRoom[];
  objs?: AdminObject[];
  strs?: AdminStructure[];
}

export interface AdminRoom {
  id: number;
  spcname: string;
  ocrname: string;
  bbox: string;
  centroid: string;
  area: number;
  areapercent: number;
}

export interface AdminObject {
  id: number;
  name: string;
  bbox: string;
  centroid: string;
}

export interface AdminStructure {
  id: number;
  name: string;
  bbox: string;
  centroid: string;
  area: string;
}

export interface SearchFloorPlanRequest {
  name?: string;
  uploaderEmail?: string;
  startDate?: string;
  endDate?: string;
  minRooms?: number;
  maxRooms?: number;
}

export interface FloorPlanDetailRequest {
  floorplanid: number;
}

// ============================================
// 통계 타입
// ============================================

export interface AdminStats {
  userCount: number;
  floorPlanCount: number;
  recentFloorPlan: number;
  totalChatCount: number;
  recentChatCount: number;
  chatRoomCount: number;
}

// ============================================
// 활동 로그 타입
// ============================================

export interface ActivityLog {
  id: number;
  type: 'USER' | 'FLOORPLAN' | 'CHATROOM' | 'CHAT';
  userName: string;
  userEmail: string;
  action: string;
  details: string;
  message?: string; // 옵셔널: 호환성을 위해
  createdAt: string;
}

export interface ChatHistoryDetail {
  id: number;
  chatRoomName: string;
  userName: string;
  userEmail: string;
  question: string;
  answer: string;
  createdAt: string;
}
