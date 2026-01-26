// ============================================
// Admin Feature - API Functions
// ============================================

import { apiClient } from '@/shared/api';
import type {
  AdminUser,
  AdminFloorPlan,
  AdminChatRoom,
  AdminStats,
  EditUserRequest,
  SearchUserRequest,
  UserDetailRequest,
  UserHistoryRequest,
  SearchFloorPlanRequest,
  FloorPlanDetailRequest,
} from '../types';

const ADMIN_BASE = '/api/admin';

// ============================================
// 유저 관련 API
// ============================================

// 전체 유저 목록 조회
export const getUsers = async (): Promise<AdminUser[]> => {
  const response = await apiClient.get<AdminUser[]>(`${ADMIN_BASE}/users`);
  return response.data;
};

// 유저 검색 (이름/이메일)
export const searchUsers = async (params: SearchUserRequest): Promise<AdminUser[]> => {
  const response = await apiClient.post<AdminUser[]>(
    `${ADMIN_BASE}/searchuser`,
    null,
    { params }
  );
  return response.data;
};

// 유저 정보 수정
export const editUser = async (params: EditUserRequest): Promise<string> => {
  const response = await apiClient.post<string>(
    `${ADMIN_BASE}/edituser`,
    null,
    { params }
  );
  return response.data;
};

// 유저 상세 조회
export const getUserDetail = async (params: UserDetailRequest): Promise<AdminUser> => {
  const response = await apiClient.post<AdminUser>(
    `${ADMIN_BASE}/userdetail`,
    null,
    { params }
  );
  return response.data;
};

// 유저 채팅 기록 조회
export const getUserHistory = async (params: UserHistoryRequest): Promise<AdminChatRoom[]> => {
  const response = await apiClient.post<AdminChatRoom[]>(
    `${ADMIN_BASE}/userhistory`,
    null,
    { params }
  );
  return response.data;
};

// ============================================
// 도면 관련 API
// ============================================

// 전체 도면 목록 조회
export const getFloorPlans = async (): Promise<AdminFloorPlan[]> => {
  const response = await apiClient.get<AdminFloorPlan[]>(`${ADMIN_BASE}/floorplans`);
  return response.data;
};

// 도면 검색 (다양한 조건)
export const searchFloorPlans = async (params: SearchFloorPlanRequest): Promise<AdminFloorPlan[]> => {
  const response = await apiClient.post<AdminFloorPlan[]>(
    `${ADMIN_BASE}/searchfloorplan`,
    null,
    { params }
  );
  return response.data;
};

// 도면 상세 조회
export const getFloorPlanDetail = async (params: FloorPlanDetailRequest): Promise<AdminFloorPlan> => {
  const response = await apiClient.post<AdminFloorPlan>(
    `${ADMIN_BASE}/floorplandetail`,
    null,
    { params }
  );
  return response.data;
};

// ============================================
// 통계 API
// ============================================

// 관리자 통계 조회
export const getAdminStats = async (): Promise<AdminStats> => {
  const response = await apiClient.get<AdminStats>(`${ADMIN_BASE}/stats`);
  return response.data;
};

// ============================================
// 삭제 API
// ============================================

// 유저 또는 도면 삭제 (일괄 삭제 지원)
export const deleteEntities = async (
  type: 'user' | 'floorplan',
  ids: number[]
): Promise<string> => {
  const response = await apiClient.post<string>(
    `${ADMIN_BASE}/deleteentities`,
    ids,
    { params: { type } }
  );
  return response.data;
};
