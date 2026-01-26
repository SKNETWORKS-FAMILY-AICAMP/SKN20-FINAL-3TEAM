import React, { useState } from 'react';
import { FiLock, FiMail, FiKey } from 'react-icons/fi';
import { BsCheckCircle } from 'react-icons/bs';
import { Input, Button } from '@/shared/components';
import { useTheme } from '@/shared/contexts';
import { sendVerificationMail, verifyMailCode, changePassword } from '@/features/auth/api';
import type { AuthView, PasswordResetStep, PasswordResetFormData } from '@/features/auth/types';
import { initialPasswordResetData } from '@/features/auth/types';
import styles from './PasswordReset.module.css';

interface PasswordResetProps {
  onViewChange: (view: AuthView) => void;
}

const PasswordReset: React.FC<PasswordResetProps> = ({ onViewChange }) => {
  const { colors } = useTheme();
  const [step, setStep] = useState<PasswordResetStep>('email-input');
  const [formData, setFormData] = useState<PasswordResetFormData>(initialPasswordResetData);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string>('');

  const handleEmailSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError('');
    setLoading(true);
    try {
      await sendVerificationMail({ email: formData.email });
      setStep('verify-code');
    } catch (err: any) {
      setError(err.response?.data?.message || '인증 메일 전송에 실패했습니다.');
    } finally {
      setLoading(false);
    }
  };

  const handleVerifyCode = async (e: React.FormEvent) => {
    e.preventDefault();
    setError('');
    setLoading(true);
    try {
      await verifyMailCode({
        mail: formData.email,
        userNumber: parseInt(formData.verificationCode, 10),
      });
      setStep('new-password');
    } catch (err: any) {
      setError(err.response?.data?.message || '인증번호가 올바르지 않습니다.');
    } finally {
      setLoading(false);
    }
  };

  const handlePasswordReset = async (e: React.FormEvent) => {
    e.preventDefault();
    setError('');
    if (formData.newPassword !== formData.confirmPassword) {
      setError('비밀번호가 일치하지 않습니다.');
      return;
    }
    if (formData.newPassword.length < 8) {
      setError('비밀번호는 8자 이상이어야 합니다.');
      return;
    }
    setLoading(true);
    try {
      await changePassword({
        email: formData.email,
        newPassword: formData.newPassword,
      });
      setStep('complete');
    } catch (err: any) {
      setError(err.response?.data?.message || '비밀번호 재설정에 실패했습니다.');
    } finally {
      setLoading(false);
    }
  };

  const StepIndicator = () => {
    const currentIndex = ['email-input', 'verify-code', 'new-password', 'complete'].indexOf(step);
    return (
      <div className={styles.stepIndicator}>
        {[0, 1, 2, 3].map((index) => (
          <div
            key={index}
            className={styles.stepDot}
            style={{ backgroundColor: index <= currentIndex ? colors.primary : colors.border }}
          />
        ))}
      </div>
    );
  };

  const renderStepContent = () => {
    switch (step) {
      case 'email-input':
        return (
          <form onSubmit={handleEmailSubmit}>
            <div className={styles.centerContent}>
              <div className={styles.icon}><FiLock size={32} /></div>
              <h2 className={styles.stepTitle} style={{ color: colors.textPrimary }}>비밀번호를 잊으셨나요?</h2>
              <p className={styles.stepDesc} style={{ color: colors.textSecondary }}>등록된 이메일로 인증번호를 보내드립니다.</p>
            </div>
            <Input label="이메일" type="email" placeholder="가입 시 등록한 이메일을 입력하세요" value={formData.email} onChange={(e) => setFormData({ ...formData, email: e.target.value })} required />
            <Button type="submit" fullWidth disabled={loading}>{loading ? '전송 중...' : '인증번호 전송'}</Button>
          </form>
        );

      case 'verify-code':
        return (
          <form onSubmit={handleVerifyCode}>
            <div className={styles.centerContent}>
              <div className={styles.icon}><FiMail size={32} /></div>
              <h2 className={styles.stepTitle} style={{ color: colors.textPrimary }}>이메일을 확인하세요</h2>
              <p className={styles.stepDesc} style={{ color: colors.textSecondary }}>
                인증번호가 전송되었습니다<br />
                <strong style={{ color: colors.textPrimary }}>{formData.email}</strong>
              </p>
            </div>
            <Input label="인증번호" type="text" placeholder="6자리 인증번호 입력" value={formData.verificationCode} onChange={(e) => setFormData({ ...formData, verificationCode: e.target.value })} required />
            <Button type="submit" fullWidth disabled={loading}>{loading ? '확인 중...' : '인증하기'}</Button>
            <div className={styles.resendWrap}>
              <button type="button" onClick={handleEmailSubmit} className={styles.linkButton} style={{ color: colors.primary }}>인증번호 재전송</button>
            </div>
          </form>
        );

      case 'new-password':
        return (
          <form onSubmit={handlePasswordReset}>
            <div className={styles.centerContent}>
              <div className={styles.icon}><FiKey size={32} /></div>
              <h2 className={styles.stepTitle} style={{ color: colors.textPrimary }}>새 비밀번호 설정</h2>
            </div>
            <div className={styles.passwordRules} style={{ backgroundColor: colors.inputBg }}>
              <p className={styles.rulesTitle} style={{ color: colors.textPrimary }}>비밀번호 조건</p>
              <ul className={styles.rulesList} style={{ color: colors.textSecondary }}>
                <li>8~15자 길이</li>
                <li>영문, 숫자, 특수문자 포함</li>
                <li>연속된 동일 문자 3자 이상 사용 불가</li>
              </ul>
            </div>
            <Input label="새 비밀번호" type="password" placeholder="새 비밀번호를 입력하세요" value={formData.newPassword} onChange={(e) => setFormData({ ...formData, newPassword: e.target.value })} required showPasswordToggle />
            <Input label="비밀번호 확인" type="password" placeholder="비밀번호를 다시 입력하세요" value={formData.confirmPassword} onChange={(e) => setFormData({ ...formData, confirmPassword: e.target.value })} required showPasswordToggle />
            <Button type="submit" fullWidth disabled={loading}>{loading ? '변경 중...' : '비밀번호 변경'}</Button>
          </form>
        );

      case 'complete':
        return (
          <div className={styles.centerContent}>
            <div className={styles.iconLarge}><BsCheckCircle size={48} color="#10B981" /></div>
            <h2 className={styles.completeTitle} style={{ color: colors.textPrimary }}>비밀번호 변경 완료</h2>
            <p className={styles.completeDesc} style={{ color: colors.textSecondary }}>비밀번호가 성공적으로 변경되었습니다.<br />새 비밀번호로 로그인해주세요.</p>
            <Button fullWidth onClick={() => onViewChange('login')}>로그인하기</Button>
          </div>
        );

      default:
        return null;
    }
  };

  return (
    <div>
      <h1 className={styles.title} style={{ color: colors.textPrimary }}>비밀번호 재설정</h1>
      <StepIndicator />
      {error && (
        <div className={styles.errorBox} style={{ backgroundColor: '#FEE2E2', borderColor: colors.error, color: '#991B1B' }}>
          {error}
        </div>
      )}
      {renderStepContent()}
      {step === 'email-input' && (
        <div className={styles.footer} style={{ borderTopColor: colors.border, color: colors.textSecondary }}>
          비밀번호가 기억나셨나요?{' '}
          <button type="button" onClick={() => onViewChange('login')} className={styles.linkButton} style={{ color: colors.primary, fontWeight: 600 }}>로그인</button>
        </div>
      )}
    </div>
  );
};

export default PasswordReset;
