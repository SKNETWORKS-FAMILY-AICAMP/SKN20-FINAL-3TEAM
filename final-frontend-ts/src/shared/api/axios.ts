// ============================================
// Axios 인스턴스 설정
// ============================================

import axios, { AxiosError } from 'axios';
import type { AxiosInstance, InternalAxiosRequestConfig } from 'axios';
import { getToken, removeToken } from '@/shared/utils/tokenManager';

// ======== 환경 변수 설정 ========
// 실제 배포 시 .env 파일에서 관리
const BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8080';

// ======== Axios 인스턴스 생성 ========
const apiClient: AxiosInstance = axios.create({
  baseURL: BASE_URL,
  timeout: 10000, // 10초
  headers: {
    'Content-Type': 'application/json',
  },
});

// ======== Request 인터셉터 ========
// 모든 요청에 자동으로 JWT 토큰 포함
apiClient.interceptors.request.use(
  (config: InternalAxiosRequestConfig) => {
    const token = getToken();

    // 토큰이 있으면 Authorization 헤더 추가
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
    // 성공 응답은 그대로 반환
    return response;
  },
  (error: AxiosError) => {
    // 401 Unauthorized: 토큰 만료 또는 인증 실패
    if (error.response?.status === 401) {
      console.error('인증 오류: 토큰이 만료되었거나 유효하지 않습니다.');

      // 토큰 삭제
      removeToken();

      // 로그인 페이지로 리다이렉트
      // window.location.href = '/login';
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
