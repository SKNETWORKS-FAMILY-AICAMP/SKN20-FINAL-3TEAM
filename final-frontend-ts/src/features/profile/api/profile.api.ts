import apiClient from '@/shared/api/axios';
import type { MyFloorPlan, FloorPlanDetail } from '../types/profile.types';

export const getMyFloorPlans = async (): Promise<MyFloorPlan[]> => {
  const response = await apiClient.get<MyFloorPlan[]>('/api/floorplan/my');
  return response.data;
};

export const getFloorPlanDetail = async (id: number): Promise<FloorPlanDetail> => {
  const response = await apiClient.get<FloorPlanDetail>(`/api/floorplan/${id}/detail`);
  return response.data;
};
