// ============================================
// Auth Feature - Type Definitions
// ============================================

// ---------- View & Step Types ----------
export type AuthView = 'login' | 'signup' | 'forgot-password' | 'reset-password';

export type SignupStep =
  | 'user-info'
  | 'email-request'
  | 'verify-code'
  | 'password-setup'
  | 'complete';

export type PasswordResetStep =
  | 'email-input'
  | 'verify-code'
  | 'new-password'
  | 'complete';

// ---------- Form Data Interfaces ----------
export interface LoginFormData {
  email: string;
  password: string;
}

export interface SignupFormData {
  name: string;
  email: string;
  phone: string;
  verificationCode: string;
  password: string;
  confirmPassword: string;
}

export interface PasswordResetFormData {
  email: string;
  verificationCode: string;
  newPassword: string;
  confirmPassword: string;
}

// ---------- Initial Form Data ----------
export const initialLoginData: LoginFormData = {
  email: '',
  password: '',
};

export const initialSignupData: SignupFormData = {
  name: '',
  email: '',
  phone: '',
  verificationCode: '',
  password: '',
  confirmPassword: '',
};

export const initialPasswordResetData: PasswordResetFormData = {
  email: '',
  verificationCode: '',
  newPassword: '',
  confirmPassword: '',
};

// ---------- API Request Types ----------
export interface LoginRequest {
  email: string;
  password: string;
}

export interface SignupRequest {
  email: string;
  pw: string;
  name: string;
  phonenumber: string;
}

export interface CheckEmailRequest {
  email: string;
}

export interface MailSendRequest {
  email: string;
}

export interface MailCheckRequest {
  mail: string;
  userNumber: number;
}

export interface ProfileUpdateRequest {
  name: string;
  phonenumber: string;
}

export interface ChangePasswordRequest {
  email: string;
  newPassword: string;
}

// ---------- API Response Types ----------
export interface LoginResponse {
  token: string;
  type: string;
  email: string;
  username: string;
  role: string;
}

export interface SignupResponse {
  success: boolean;
  message: string;
}

export interface MailSendResponse {
  success: boolean;
  message: string;
}

export interface MailCheckResponse {
  success: boolean;
  message: string;
}

export interface UserInfoResponse {
  email: string;
  name: string;
  phonenumber: number;
  role: string;
}

export interface ProfileUpdateResponse {
  success: boolean;
  message: string;
}

export interface ChangePasswordResponse {
  success: boolean;
  message: string;
}
