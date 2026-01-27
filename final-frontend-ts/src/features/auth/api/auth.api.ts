// ============================================
// Auth Feature - API Functions
// ============================================

import apiClient from '@/shared/api/axios';
import { setToken, setUserInfo } from '@/shared/utils/tokenManager';
import type {
  LoginRequest,
  LoginResponse,
  SignupRequest,
  SignupResponse,
  CheckEmailRequest,
  MailSendRequest,
  MailSendResponse,
  MailCheckRequest,
  MailCheckResponse,
  UserInfoResponse,
  ProfileUpdateRequest,
  ProfileUpdateResponse,
  ChangePasswordRequest,
  ChangePasswordResponse,
} from '../types/auth.types';

const AUTH_BASE = '/api/auth';

// ============================================
// 1. 이메일 중복 검사
// ============================================
export const checkEmail = async (data: CheckEmailRequest): Promise<string> => {
  const response = await apiClient.post<string>(
    `${AUTH_BASE}/check-email`,
    data
  );
  return response.data;
};

// ============================================
// 2. 회원가입
// ============================================
export const signup = async (data: SignupRequest): Promise<SignupResponse> => {
  const response = await apiClient.post<SignupResponse>(
    `${AUTH_BASE}/signup`,
    data
  );
  return response.data;
};

// ============================================
// 3. 로그인
// ============================================
export const login = async (data: LoginRequest): Promise<LoginResponse> => {
  const response = await apiClient.post<LoginResponse>(
    `${AUTH_BASE}/login`,
    data
  );

  const result = response.data;

  // 로그인 성공 시 토큰 저장
  if (result.token) {
    setToken(result.token);
    setUserInfo({
      email: result.email,
      username: result.username,
      role: result.role,
    });
  }

  return result;
};

// ============================================
// 4. 현재 로그인 사용자 정보 조회
// ============================================
export const getCurrentUser = async (): Promise<UserInfoResponse> => {
  const response = await apiClient.get<UserInfoResponse>(`${AUTH_BASE}/me`);
  return response.data;
};

// ============================================
// 5. 프로필 수정
// ============================================
export const updateProfile = async (
  data: ProfileUpdateRequest
): Promise<ProfileUpdateResponse> => {
  const response = await apiClient.post<ProfileUpdateResponse>(
    `${AUTH_BASE}/profile`,
    data
  );
  return response.data;
};

// ============================================
// 6. 비밀번호 변경
// ============================================
export const changePassword = async (
  data: ChangePasswordRequest
): Promise<ChangePasswordResponse> => {
  const response = await apiClient.post<ChangePasswordResponse>(
    `${AUTH_BASE}/change-password`,
    data
  );
  return response.data;
};

// ============================================
// 7. 인증 이메일 발송
// ============================================
export const sendVerificationMail = async (
  data: MailSendRequest
): Promise<MailSendResponse> => {
  const response = await apiClient.post<MailSendResponse>(
    `${AUTH_BASE}/mailSend`,
    data
  );
  return response.data;
};

// ============================================
// 8. 이메일 인증번호 확인
// ============================================
export const verifyMailCode = async (
  params: MailCheckRequest
): Promise<MailCheckResponse> => {
  const response = await apiClient.get<MailCheckResponse>(
    `${AUTH_BASE}/mailCheck`,
    { params }
  );
  return response.data;
};
