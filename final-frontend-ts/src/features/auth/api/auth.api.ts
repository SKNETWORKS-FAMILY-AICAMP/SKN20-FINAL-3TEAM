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
export const checkEmail = async (params: CheckEmailRequest): Promise<string> => {
  const response = await apiClient.post<string>(
    `${AUTH_BASE}/check-email`,
    null,
    { params }
  );
  return response.data;
};

// ============================================
// 2. 회원가입
// ============================================
export const signup = async (params: SignupRequest): Promise<SignupResponse> => {
  const response = await apiClient.post<SignupResponse>(
    `${AUTH_BASE}/signup`,
    null,
    { params }
  );
  return response.data;
};

// ============================================
// 3. 로그인
// ============================================
export const login = async (params: LoginRequest): Promise<LoginResponse> => {
  const response = await apiClient.post<LoginResponse>(
    `${AUTH_BASE}/login`,
    null,
    { params }
  );

  const data = response.data;

  // 로그인 성공 시 토큰 저장
  if (data.token) {
    setToken(data.token);
    setUserInfo({
      email: data.email,
      username: data.username,
      role: data.role,
    });
  }

  return data;
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
  params: ProfileUpdateRequest
): Promise<ProfileUpdateResponse> => {
  const response = await apiClient.post<ProfileUpdateResponse>(
    `${AUTH_BASE}/profile`,
    null,
    { params }
  );
  return response.data;
};

// ============================================
// 6. 비밀번호 변경
// ============================================
export const changePassword = async (
  params: ChangePasswordRequest
): Promise<ChangePasswordResponse> => {
  const response = await apiClient.post<ChangePasswordResponse>(
    `${AUTH_BASE}/change-password`,
    null,
    { params }
  );
  return response.data;
};

// ============================================
// 7. 인증 이메일 발송
// ============================================
export const sendVerificationMail = async (
  params: MailSendRequest
): Promise<MailSendResponse> => {
  const response = await apiClient.post<MailSendResponse>(
    `${AUTH_BASE}/mailSend`,
    null,
    { params }
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
