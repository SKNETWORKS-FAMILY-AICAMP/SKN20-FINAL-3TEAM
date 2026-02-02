import { useEffect, useRef } from 'react';
import type { ReactNode } from 'react';
import { Navigate, useLocation } from 'react-router-dom';
import toast from 'react-hot-toast';
import { useAuth } from '@/shared/contexts/AuthContext';

interface ProtectedRouteProps {
  children: ReactNode;
}

const ProtectedRoute = ({ children }: ProtectedRouteProps) => {
  // TODO: 테스트 후 아래 주석 해제
  return <>{children}</>;  // 임시: 인증 우회

  const { isAuthenticated, isLoading } = useAuth();
  const location = useLocation();
  const hasShownToast = useRef(false);

  useEffect(() => {
    // 로딩 중일 때는 토스트를 표시하지 않음
    if (!isLoading && !isAuthenticated && !hasShownToast.current) {
      hasShownToast.current = true;
      toast.error('로그인이 필요한 페이지입니다.', {
        duration: 3000,
        position: 'top-center',
        style: {
          background: '#FEE2E2',
          color: '#991B1B',
          fontWeight: 500,
          padding: '16px 24px',
          borderRadius: '12px',
          border: '1px solid #FECACA',
        },
        icon: '🔒',
      });
    }
  }, [isAuthenticated, isLoading]);

  // 로딩 중일 때는 잠시 대기 (토큰 확인 중)
  if (isLoading) {
    return null;
  }

  if (!isAuthenticated) {
    // 현재 위치를 state로 전달해서 로그인 후 돌아올 수 있게 함
    return <Navigate to="/auth" state={{ from: location }} replace />;
  }

  return <>{children}</>;
};

export default ProtectedRoute;
