import { createContext, useContext, useState, useEffect } from 'react';
import type { ReactNode } from 'react';
import { getToken, getUserInfo, setToken as saveToken, setUserInfo, removeToken } from '@/shared/utils/tokenManager';

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

export const AuthProvider = ({ children }: { children: ReactNode }) => {
  const [user, setUser] = useState<User | null>(null);
  const [token, setToken] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(true);

  // 앱 시작 시 localStorage에서 인증 정보 복원 (tokenManager 사용)
  useEffect(() => {
    const savedToken = getToken();
    const savedUser = getUserInfo();

    if (savedToken) {
      setToken(savedToken);
      setUser(savedUser);
    }
    setIsLoading(false);
  }, []);

  const login = (newToken: string, newUser: User, rememberMe: boolean = false) => {
    setToken(newToken);
    setUser(newUser);
    saveToken(newToken, rememberMe);
    setUserInfo(newUser, rememberMe);
  };

  const logout = () => {
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
