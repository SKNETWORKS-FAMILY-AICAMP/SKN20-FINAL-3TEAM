// ============================================
// Admin Feature - API Functions
// ============================================

import apiClient from '@/shared/api/axios';
import type {
  AdminFloorPlan,
  AdminStats,
  ActivityLog,
  ChatHistoryDetail,
  SearchFloorPlanRequest,
  FloorPlanDetailRequest,
} from '../types/admin.types';

const ADMIN_BASE = '/api/admin';

// ============================================
// 통계 API
// ============================================

// 관리자 통계 조회
export const getAdminStats = async (): Promise<AdminStats> => {
  const response = await apiClient.get<AdminStats>(`${ADMIN_BASE}/stats`);
  return response.data;
};

// ============================================
// 활동 로그 API
// ============================================

// 활동 로그 조회 (도면 업로드 + 챗봇 사용)
export const getActivityLogs = async (): Promise<ActivityLog[]> => {
  const response = await apiClient.get<ActivityLog[]>(`${ADMIN_BASE}/logs`);
  return response.data;
};

// 챗봇 대화 상세 조회
export const getChatHistoryDetail = async (id: number): Promise<ChatHistoryDetail> => {
  const response = await apiClient.get<ChatHistoryDetail>(`${ADMIN_BASE}/chathistory/${id}`);
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
// 삭제 API
// ============================================

// 도면 삭제 (일괄 삭제 지원)
export const deleteEntities = async (
  type: 'floorplan',
  ids: number[]
): Promise<string> => {
  const response = await apiClient.post<string>(
    `${ADMIN_BASE}/deleteentities`,
    ids,
    { params: { type } }
  );
  return response.data;
};
