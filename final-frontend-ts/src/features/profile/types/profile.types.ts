// ============================================
// Profile Feature - Type Definitions
// ============================================

// 사용자 타입
export interface User {
  id: string;
  name: string;
  email: string;
  position: string;
  phone: string;
  record?: string;
}

// 프로필 편집 상태
export interface ProfileEditState {
  isEditing: boolean;
  isSaving: boolean;
}
