// ============================================
// JWT 토큰 관리 유틸리티
// ============================================

const TOKEN_KEY = 'auth_token';
const USER_INFO_KEY = 'user_info';

/**
 * 토큰을 localStorage에 저장
 */
export const setToken = (token: string): void => {
  localStorage.setItem(TOKEN_KEY, token);
};

/**
 * localStorage에서 토큰 가져오기
 */
export const getToken = (): string | null => {
  return localStorage.getItem(TOKEN_KEY);
};

/**
 * 토큰 삭제 (로그아웃 시)
 */
export const removeToken = (): void => {
  localStorage.removeItem(TOKEN_KEY);
  localStorage.removeItem(USER_INFO_KEY);
};

/**
 * 토큰 존재 여부 확인
 */
export const hasToken = (): boolean => {
  return !!getToken();
};

/**
 * 사용자 정보 저장
 */
export const setUserInfo = (userInfo: any): void => {
  localStorage.setItem(USER_INFO_KEY, JSON.stringify(userInfo));
};

/**
 * 사용자 정보 가져오기
 */
export const getUserInfo = (): any | null => {
  const userInfo = localStorage.getItem(USER_INFO_KEY);
  return userInfo ? JSON.parse(userInfo) : null;
};

/**
 * 로그아웃 (토큰 및 사용자 정보 모두 삭제)
 */
export const logout = (): void => {
  removeToken();
  // 필요 시 추가 정리 작업
};
