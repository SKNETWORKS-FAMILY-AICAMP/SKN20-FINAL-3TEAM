// ============================================
// JWT 토큰 관리 유틸리티
// ============================================

const TOKEN_KEY = 'auth_token';
const USER_INFO_KEY = 'user_info';
const REMEMBER_KEY = 'remember_me';

/**
 * 저장소 선택 (rememberMe에 따라 localStorage 또는 sessionStorage)
 */
const getStorage = (): Storage => {
  const remember = localStorage.getItem(REMEMBER_KEY) === 'true';
  return remember ? localStorage : sessionStorage;
};

/**
 * 토큰 저장 (rememberMe에 따라 저장소 선택)
 */
export const setToken = (token: string, rememberMe: boolean = false): void => {
  // rememberMe 설정 저장 (항상 localStorage에)
  localStorage.setItem(REMEMBER_KEY, String(rememberMe));

  // 토큰은 선택된 저장소에
  const storage = rememberMe ? localStorage : sessionStorage;
  storage.setItem(TOKEN_KEY, token);
};

/**
 * 토큰 가져오기 (두 저장소 모두 확인)
 */
export const getToken = (): string | null => {
  return localStorage.getItem(TOKEN_KEY) || sessionStorage.getItem(TOKEN_KEY);
};

/**
 * 토큰 삭제 (로그아웃 시 - 양쪽 저장소 모두)
 */
export const removeToken = (): void => {
  localStorage.removeItem(TOKEN_KEY);
  localStorage.removeItem(USER_INFO_KEY);
  localStorage.removeItem(REMEMBER_KEY);
  sessionStorage.removeItem(TOKEN_KEY);
  sessionStorage.removeItem(USER_INFO_KEY);
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
export const setUserInfo = (userInfo: any, rememberMe: boolean = false): void => {
  const storage = rememberMe ? localStorage : sessionStorage;
  storage.setItem(USER_INFO_KEY, JSON.stringify(userInfo));
};

/**
 * 사용자 정보 가져오기
 */
export const getUserInfo = (): any | null => {
  const userInfo = localStorage.getItem(USER_INFO_KEY) || sessionStorage.getItem(USER_INFO_KEY);
  return userInfo ? JSON.parse(userInfo) : null;
};

/**
 * 로그아웃 (토큰 및 사용자 정보 모두 삭제)
 */
export const logout = (): void => {
  removeToken();
};

// ============================================
// 전화번호 유틸리티
// ============================================

/**
 * 전화번호를 화면 표시용 형식으로 변환
 * 1012345678 → 010-1234-5678
 */
export const formatPhoneNumber = (phone: number | undefined): string => {
  if (!phone) return '';
  let str = phone.toString();

  // 10자리면 앞에 0 추가 (010으로 시작하는 번호가 Integer로 저장되면서 앞 0이 사라진 경우)
  if (str.length === 10) {
    str = '0' + str;
  }

  // 11자리: 010-1234-5678
  if (str.length === 11) {
    return `${str.slice(0, 3)}-${str.slice(3, 7)}-${str.slice(7)}`;
  }

  return str;
};

/**
 * 전화번호 문자열을 숫자로 변환 (API 전송용)
 * 010-1234-5678 → 1012345678
 */
export const parsePhoneNumber = (phone: string): number => {
  return parseInt(phone.replace(/-/g, ''), 10) || 0;
};
