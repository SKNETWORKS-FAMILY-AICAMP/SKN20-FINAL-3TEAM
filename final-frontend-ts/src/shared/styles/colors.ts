// 색상 팔레트 정의

// 라이트 모드 색상
export const lightColors = {
  primary: '#FF8C42',       // 오렌지
  primaryHover: '#FF7A2E',  // 오렌지 호버
  secondary: '#6B7280',     // 회색
  background: '#F3F4F6',    // 연한 회색 배경
  white: '#FFFFFF',
  black: '#000000',
  textPrimary: '#1F2937',   // 진한 회색 텍스트
  textSecondary: '#6B7280', // 중간 회색 텍스트
  border: '#E5E7EB',        // 테두리
  inputBg: '#F9FAFB',       // 입력창 배경
  success: '#10B981',       // 성공 메시지
  error: '#EF4444',         // 에러 메시지
  logoGray: '#9CA3AF',      // 로고 회색
  chatBg: '#EFF6FF',        // 채팅 배경
  sidebarBg: '#FFFFFF',     // 사이드바 배경
  cardBg: '#FFFFFF',        // 카드 배경
};

// 다크 모드 색상
export const darkColors = {
  primary: '#FF8C42',       // 오렌지 (유지)
  primaryHover: '#FF9F5A',  // 오렌지 호버 (밝게)
  secondary: '#9CA3AF',     // 회색 (밝게)
  background: '#4d525d',    // 진한 네이비 배경
  white: '#1f2b37',         // 다크 카드 배경
  black: '#FFFFFF',         // 반전
  textPrimary: '#F9FAFB',   // 밝은 텍스트
  textSecondary: '#9CA3AF', // 중간 밝기 텍스트
  border: '#374151',        // 어두운 테두리
  inputBg: '#1F2937',       // 어두운 입력창 배경
  success: '#34D399',       // 성공 메시지 (밝게)
  error: '#F87171',         // 에러 메시지 (밝게)
  logoGray: '#6B7280',      // 로고 회색
  chatBg: '#1E3A5F',        // 어두운 채팅 배경
  sidebarBg: '#1F2937',     // 어두운 사이드바 배경
  cardBg: '#1F2937',        // 카드 배경
};

// 테마 타입 정의
export type ThemeColors = typeof lightColors;

// 기본 내보내기 (라이트 모드)
export const colors = lightColors;
