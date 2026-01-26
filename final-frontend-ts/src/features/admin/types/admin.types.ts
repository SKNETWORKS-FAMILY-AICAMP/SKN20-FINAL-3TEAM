// ============================================
// Admin Feature - Type Definitions
// ============================================

// ============================================
// User 관련 타입
// ============================================

export interface AdminUser {
  id: number;
  email: string;
  name: string;
  phonenumber: number;
  role: string;
  create_at: string;
  update_at: string;
}

export interface EditUserRequest {
  userid: number;
  name?: string;
  phone?: number;
  role?: string;
}

export interface SearchUserRequest {
  search: string;
}

export interface UserDetailRequest {
  userid: number;
}

export interface UserHistoryRequest {
  userid: number;
}

// ============================================
// FloorPlan 관련 타입
// ============================================

export interface AdminFloorPlan {
  id: number;
  name: string;
  imageUrl: string;
  user: AdminUser;
  createdAt: string;
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
  imageUrl?: string;
  startDate?: string;
  endDate?: string;
  minRooms?: number;
  maxRooms?: number;
  roomName?: string;
  objName?: string;
  strName?: string;
}

export interface FloorPlanDetailRequest {
  floorplanid: number;
}

// ============================================
// ChatRoom 관련 타입 (유저 채팅 기록용) - 백엔드 엔티티와 일치
// ============================================

export interface AdminChatRoom {
  id: number;
  name: string;
  createdAt: string;
  user: AdminUser;
}

// ============================================
// 통계 타입
// ============================================

export interface AdminStats {
  userCount: number;
  floorPlanCount: number;
  recentFloorPlan: number;
}

// ============================================
// 삭제 요청 타입
// ============================================

export interface DeleteEntitiesRequest {
  type: 'user' | 'floorplan';
  ids: number[];
}
