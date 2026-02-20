// ============================================
// Profile Feature - Type Definitions
// ============================================

// 사용자 타입 (백엔드 User 엔티티와 일치)
export interface User {
  id: number;
  email: string;
  name: string;
  phonenumber: number;
  role: string;
  create_at?: string;
  update_at?: string;
}

// 도면 분석 내역
export interface MyFloorPlan {
  id: number;
  name: string;
  createdAt: string;
}

// 도면 상세 정보
export interface FloorPlanDetail {
  id: number;
  name: string;
  createdAt: string;
  imageUrl: string;
  assessmentJson: string | null;
}

// 프로필 편집 상태
export interface ProfileEditState {
  isEditing: boolean;
  isSaving: boolean;
}
