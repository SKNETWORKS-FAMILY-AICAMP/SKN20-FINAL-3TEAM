// ============================================
// FloorPlan Feature - API Functions
// ============================================

import apiClient from '@/shared/api/axios';
import type {
  FloorPlanUploadResponse,
  FloorPlanSaveResponse,
} from '../types/floor-plan.types';

const FLOORPLAN_BASE = '/api/floorplan';

// ============================================
// 1. 도면 이미지 업로드 및 분석
// ============================================
export const uploadFloorPlan = async (
  file: File
): Promise<FloorPlanUploadResponse> => {
  const formData = new FormData();
  formData.append('file', file);

  const response = await apiClient.post<FloorPlanUploadResponse>(
    `${FLOORPLAN_BASE}/imgupload`,
    formData,
    {
      headers: {
        'Content-Type': 'multipart/form-data',
      },
    }
  );
  return response.data;
};

// ============================================
// 2. 도면 분석 결과 저장
// ============================================
export const saveFloorPlan = async (
  data: object
): Promise<FloorPlanSaveResponse> => {
  const response = await apiClient.post<FloorPlanSaveResponse>(
    `${FLOORPLAN_BASE}/save`,
    null,
    {
      params: {
        data: JSON.stringify(data),
      },
    }
  );
  return response.data;
};
