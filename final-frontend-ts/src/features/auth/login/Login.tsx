import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import Input from '@/shared/components/Input/Input';
import Button from '@/shared/components/Button/Button';
import { useTheme } from '@/shared/contexts/ThemeContext';
import { useAuth } from '@/shared/contexts/AuthContext';
import { login as loginApi } from '@/features/auth/api/auth.api';
import type { AuthView, LoginFormData } from '@/features/auth/types/auth.types';
import { initialLoginData } from '@/features/auth/types/auth.types';
import styles from './Login.module.css';

interface LoginProps {
  onViewChange: (view: AuthView) => void;
}

const Login: React.FC<LoginProps> = ({ onViewChange }) => {
  const navigate = useNavigate();
  const { colors } = useTheme();
  const { login } = useAuth();
  const [formData, setFormData] = useState<LoginFormData>(initialLoginData);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string>('');

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError('');
    setLoading(true);

    try {
      const response = await loginApi({
        email: formData.email,
        password: formData.password,
      });

      // AuthContext에 로그인 정보 저장
      login(response.token, {
        email: response.email,
        username: response.username,
        role: response.role,
      });

      navigate('/main');
    } catch (err: any) {
      console.error('Login failed:', err);
      setError(err.response?.data?.message || '로그인에 실패했습니다. 다시 시도해주세요.');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div>
      <h1 className={styles.title} style={{ color: colors.textPrimary }}>
        로그인
      </h1>

      <form onSubmit={handleSubmit}>
        <Input
          label="이메일"
          type="email"
          placeholder="example@email.com"
          value={formData.email}
          onChange={(e) => setFormData({ ...formData, email: e.target.value })}
          required
        />

        <Input
          label="비밀번호"
          type="password"
          placeholder="비밀번호를 입력하세요"
          value={formData.password}
          onChange={(e) => setFormData({ ...formData, password: e.target.value })}
          required
          showPasswordToggle
        />

        <p className={styles.hint} style={{ color: colors.textSecondary }}>
          영문자, 숫자, 특수문자를 포함해 8자 이상이어야 합니다.
        </p>

        <div className={styles.forgotPassword}>
          <button
            type="button"
            onClick={() => onViewChange('forgot-password')}
            className={styles.linkButton}
            style={{ color: colors.primary }}
          >
            비밀번호를 잊으셨나요?
          </button>
        </div>

        {error && (
          <div
            className={styles.errorBox}
            style={{
              backgroundColor: '#FEE2E2',
              borderColor: colors.error,
              color: '#991B1B',
            }}
          >
            {error}
          </div>
        )}

        <Button type="submit" fullWidth disabled={loading}>
          {loading ? '로그인 중...' : '로그인'}
        </Button>
      </form>

      <div
        className={styles.footer}
        style={{ borderTopColor: colors.border, color: colors.textSecondary }}
      >
        계정이 없으신가요?{' '}
        <button
          type="button"
          onClick={() => onViewChange('signup')}
          className={styles.linkButton}
          style={{ color: colors.primary, fontWeight: 600 }}
        >
          회원가입
        </button>
      </div>
    </div>
  );
};

export default Login;
