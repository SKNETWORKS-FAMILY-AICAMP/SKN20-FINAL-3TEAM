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

// 프로필 편집 상태
export interface ProfileEditState {
  isEditing: boolean;
  isSaving: boolean;
}
