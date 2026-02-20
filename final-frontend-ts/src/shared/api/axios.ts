// ============================================
// Axios 인스턴스 설정
// ============================================

import axios, { AxiosError } from 'axios';
import type { AxiosInstance, InternalAxiosRequestConfig } from 'axios';
import { getToken, setToken, getUserInfo, setUserInfo, removeToken } from '@/shared/utils/tokenManager';

// ======== 환경 변수 설정 ========
export const BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8080';

// ======== Axios 인스턴스 생성 ========
const apiClient: AxiosInstance = axios.create({
  baseURL: BASE_URL,
  timeout: 600000, // 600초 = 10분 (CV 분석에 시간이 오래 걸림)
  headers: {
    'Content-Type': 'application/json',
  },
});

// ======== JWT 만료시간 파싱 ========
function getTokenExpiration(token: string): number | null {
  try {
    const payload = JSON.parse(atob(token.split('.')[1]));
    return payload.exp ? payload.exp * 1000 : null;
  } catch {
    return null;
  }
}

// ======== 토큰 자동 갱신 ========
let isRefreshing = false;
let refreshPromise: Promise<void> | null = null;

async function refreshTokenIfNeeded(): Promise<void> {
  const token = getToken();
  if (!token) return;

  const exp = getTokenExpiration(token);
  if (!exp) return;

  const remaining = exp - Date.now();
  // 만료 5분 전이면 갱신, 이미 만료됐으면 스킵
  if (remaining > 5 * 60 * 1000 || remaining <= 0) return;

  // 동시 갱신 방지
  if (isRefreshing) {
    await refreshPromise;
    return;
  }

  isRefreshing = true;
  refreshPromise = (async () => {
    try {
      const response = await axios.post(
        `${BASE_URL}/api/auth/refresh`,
        null,
        { headers: { Authorization: `Bearer ${token}` } }
      );
      const newToken = response.data.token;
      if (newToken) {
        const rememberMe = localStorage.getItem('remember_me') === 'true';
        setToken(newToken, rememberMe);
        const userInfo = getUserInfo();
        if (userInfo) setUserInfo(userInfo, rememberMe);
      }
    } catch {
      // 갱신 실패 시 무시 (기존 토큰으로 계속 시도)
    } finally {
      isRefreshing = false;
      refreshPromise = null;
    }
  })();

  await refreshPromise;
}

// ======== Request 인터셉터 ========
// 모든 요청 전: 토큰 만료 임박 시 자동 갱신 + Authorization 헤더 추가
apiClient.interceptors.request.use(
  async (config: InternalAxiosRequestConfig) => {
    // refresh 요청 자체는 갱신 로직 스킵 (무한루프 방지)
    if (!config.url?.includes('/api/auth/refresh')) {
      await refreshTokenIfNeeded();
    }

    const token = getToken();
    if (token) {
      config.headers.Authorization = `Bearer ${token}`;
    }

    return config;
  },
  (error: AxiosError) => {
    return Promise.reject(error);
  }
);

// ======== Response 인터셉터 ========
// 전역 에러 처리
apiClient.interceptors.response.use(
  (response) => {
    return response;
  },
  (error: AxiosError) => {
    // 401 Unauthorized: 토큰 만료 또는 인증 실패
    if (error.response?.status === 401) {
      console.error('인증 오류: 토큰이 만료되었거나 유효하지 않습니다.');
      removeToken();
    }

    // 403 Forbidden: 권한 없음
    if (error.response?.status === 403) {
      console.error('권한 오류: 접근 권한이 없습니다.');
    }

    // 500 Internal Server Error
    if (error.response?.status === 500) {
      console.error('서버 오류: 잠시 후 다시 시도해주세요.');
    }

    return Promise.reject(error);
  }
);

export default apiClient;
