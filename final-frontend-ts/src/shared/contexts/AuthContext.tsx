import { createContext, useContext, useState, useEffect, useCallback, useRef } from 'react';
import type { ReactNode } from 'react';
import axios from 'axios';
import { getToken, getUserInfo, setToken as saveToken, setUserInfo, removeToken } from '@/shared/utils/tokenManager';
import { BASE_URL } from '@/shared/api/axios';

interface User {
  email: string;
  username?: string;
  role?: string;
}

interface AuthContextType {
  user: User | null;
  token: string | null;
  isAuthenticated: boolean;
  isLoading: boolean;
  login: (token: string, user: User, rememberMe?: boolean) => void;
  logout: () => void;
}

const AuthContext = createContext<AuthContextType | undefined>(undefined);

// JWT 토큰에서 만료 시간(ms) 추출
function getTokenExpiration(token: string): number | null {
  try {
    const payload = JSON.parse(atob(token.split('.')[1]));
    return payload.exp ? payload.exp * 1000 : null;
  } catch {
    return null;
  }
}

export const AuthProvider = ({ children }: { children: ReactNode }) => {
  const [user, setUser] = useState<User | null>(null);
  const [token, setToken] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const expirationTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  const handleTokenExpired = useCallback(() => {
    setToken(null);
    setUser(null);
    removeToken();

    alert('로그인이 만료되었습니다. 다시 로그인해주세요.');

    if (window.location.pathname !== '/auth') {
      window.location.href = '/auth';
    }
  }, []);

  // 사용자 마지막 활동 시간 추적
  const lastActivityRef = useRef<number>(Date.now());
  const refreshCheckIntervalRef = useRef<ReturnType<typeof setInterval> | null>(null);

  // 사용자 활동 감지 핸들러
  const handleUserActivity = useCallback(() => {
    lastActivityRef.current = Date.now();
  }, []);

  // 토큰 만료 타이머 설정
  const scheduleExpiration = useCallback((currentToken: string) => {
    // 기존 타이머 정리
    if (expirationTimerRef.current) {
      clearTimeout(expirationTimerRef.current);
      expirationTimerRef.current = null;
    }

    const exp = getTokenExpiration(currentToken);
    if (!exp) return;

    const remaining = exp - Date.now();

    // 이미 만료된 토큰
    if (remaining <= 0) {
      handleTokenExpired();
      return;
    }

    // 만료 시점에 자동 로그아웃 예약
    expirationTimerRef.current = setTimeout(() => {
      handleTokenExpired();
    }, remaining);
  }, [handleTokenExpired]);

  // 토큰 갱신 (활동 중일 때 만료 전에 자동 호출)
  const refreshToken = useCallback(async (currentToken: string) => {
    try {
      const response = await axios.post(
        `${BASE_URL}/api/auth/refresh`,
        null,
        { headers: { Authorization: `Bearer ${currentToken}` } }
      );
      const newToken = response.data.token;
      if (newToken) {
        const rememberMe = localStorage.getItem('remember_me') === 'true';
        setToken(newToken);
        saveToken(newToken, rememberMe);
        const userInfo = getUserInfo();
        if (userInfo) setUserInfo(userInfo, rememberMe);
        // 새 토큰으로 만료 타이머 재설정
        scheduleExpiration(newToken);
      }
    } catch {
      // 갱신 실패 → 만료 타이머가 알아서 처리
    }
  }, [scheduleExpiration]);

  // 앱 시작 시 localStorage에서 인증 정보 복원 (tokenManager 사용)
  useEffect(() => {
    const savedToken = getToken();
    const savedUser = getUserInfo();

    if (savedToken) {
      const exp = getTokenExpiration(savedToken);
      // 이미 만료된 토큰이면 제거
      if (exp && exp <= Date.now()) {
        removeToken();
        alert('로그인이 만료되었습니다. 다시 로그인해주세요.');
      } else {
        setToken(savedToken);
        setUser(savedUser);
        scheduleExpiration(savedToken);
      }
    }
    setIsLoading(false);
  }, [scheduleExpiration]);

  // 사용자 활동 감지 + 만료 전 자동 갱신
  useEffect(() => {
    // 활동 이벤트 등록
    const events = ['mousedown', 'keydown', 'scroll', 'touchstart'];
    events.forEach((e) => window.addEventListener(e, handleUserActivity));

    // 1분마다 토큰 만료 임박 여부 체크
    refreshCheckIntervalRef.current = setInterval(() => {
      const currentToken = getToken();
      if (!currentToken) return;

      const exp = getTokenExpiration(currentToken);
      if (!exp) return;

      const remaining = exp - Date.now();
      const timeSinceLastActivity = Date.now() - lastActivityRef.current;

      // 만료 5분 전 + 최근 5분 내 활동 있음 → 자동 갱신
      if (remaining > 0 && remaining <= 5 * 60 * 1000 && timeSinceLastActivity < 5 * 60 * 1000) {
        refreshToken(currentToken);
      }
    }, 60 * 1000);

    return () => {
      events.forEach((e) => window.removeEventListener(e, handleUserActivity));
      if (refreshCheckIntervalRef.current) {
        clearInterval(refreshCheckIntervalRef.current);
      }
      if (expirationTimerRef.current) {
        clearTimeout(expirationTimerRef.current);
      }
    };
  }, [handleUserActivity, refreshToken]);

  const login = (newToken: string, newUser: User, rememberMe: boolean = false) => {
    setToken(newToken);
    setUser(newUser);
    saveToken(newToken, rememberMe);
    setUserInfo(newUser, rememberMe);
    scheduleExpiration(newToken);
  };

  const logout = () => {
    if (expirationTimerRef.current) {
      clearTimeout(expirationTimerRef.current);
      expirationTimerRef.current = null;
    }
    setToken(null);
    setUser(null);
    removeToken();
  };

  return (
    <AuthContext.Provider
      value={{
        user,
        token,
        isAuthenticated: !!token,
        isLoading,
        login,
        logout,
      }}
    >
      {children}
    </AuthContext.Provider>
  );
};

export const useAuth = () => {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error('useAuth must be used within an AuthProvider');
  }
  return context;
};
