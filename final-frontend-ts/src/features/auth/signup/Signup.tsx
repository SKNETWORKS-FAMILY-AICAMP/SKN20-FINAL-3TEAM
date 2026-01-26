import React, { useState } from 'react';
import { FiMail, FiLock, FiKey } from 'react-icons/fi';
import { BsCheckCircle } from 'react-icons/bs';
import { Input, Button } from '@/shared/components';
import { useTheme } from '@/shared/contexts';
import { checkEmail, sendVerificationMail, verifyMailCode, signup } from '@/features/auth/api';
import type { AuthView, SignupStep, SignupFormData } from '@/features/auth/types';
import { initialSignupData } from '@/features/auth/types';
import styles from './Signup.module.css';

interface SignupProps {
  onViewChange: (view: AuthView) => void;
}

const Signup: React.FC<SignupProps> = ({ onViewChange }) => {
  const { colors } = useTheme();
  const [step, setStep] = useState<SignupStep>('user-info');
  const [formData, setFormData] = useState<SignupFormData>(initialSignupData);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string>('');

  const handleUserInfoSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError('');
    setLoading(true);
    try {
      await checkEmail({ email: formData.email });
      setStep('email-request');
    } catch (err: any) {
      setError(err.response?.data?.message || '이미 등록된 이메일입니다.');
    } finally {
      setLoading(false);
    }
  };

  const handleSendVerification = async () => {
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
      setStep('password-setup');
    } catch (err: any) {
      setError(err.response?.data?.message || '인증번호가 올바르지 않습니다.');
    } finally {
      setLoading(false);
    }
  };

  const handlePasswordSetup = async (e: React.FormEvent) => {
    e.preventDefault();
    setError('');
    if (formData.password !== formData.confirmPassword) {
      setError('비밀번호가 일치하지 않습니다.');
      return;
    }
    if (formData.password.length < 8) {
      setError('비밀번호는 8자 이상이어야 합니다.');
      return;
    }
    setLoading(true);
    try {
      await signup({
        name: formData.name,
        email: formData.email,
        pw: formData.password,
        phonenumber: formData.phone,
      });
      setStep('complete');
    } catch (err: any) {
      setError(err.response?.data?.message || '회원가입에 실패했습니다.');
    } finally {
      setLoading(false);
    }
  };

  const StepIndicator = () => {
    const currentIndex = ['user-info', 'email-request', 'verify-code', 'password-setup', 'complete'].indexOf(step);
    return (
      <div className={styles.stepIndicator}>
        {[0, 1, 2, 3, 4].map((index) => (
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
      case 'user-info':
        return (
          <form onSubmit={handleUserInfoSubmit}>
            <Input label="이름" type="text" placeholder="이름을 입력하세요" value={formData.name} onChange={(e) => setFormData({ ...formData, name: e.target.value })} required />
            <Input label="이메일" type="email" placeholder="example@email.com" value={formData.email} onChange={(e) => setFormData({ ...formData, email: e.target.value })} required />
            <Input label="전화번호" type="tel" placeholder="010-0000-0000" value={formData.phone} onChange={(e) => setFormData({ ...formData, phone: e.target.value })} required />
            <Button type="submit" fullWidth disabled={loading}>{loading ? '확인 중...' : '다음'}</Button>
          </form>
        );

      case 'email-request':
        return (
          <div className={styles.centerContent}>
            <div className={styles.icon}><FiMail size={32} /></div>
            <h2 className={styles.stepTitle} style={{ color: colors.textPrimary }}>이메일 인증</h2>
            <p className={styles.stepDesc} style={{ color: colors.textSecondary }}>
              아래 이메일로 인증번호를 보내드립니다<br />
              <strong style={{ color: colors.textPrimary }}>{formData.email}</strong>
            </p>
            <Button fullWidth onClick={handleSendVerification} disabled={loading}>{loading ? '전송 중...' : '인증번호 전송'}</Button>
            <button type="button" onClick={() => setStep('user-info')} className={styles.backButton} style={{ color: colors.textSecondary }}>← 정보 수정하기</button>
          </div>
        );

      case 'verify-code':
        return (
          <form onSubmit={handleVerifyCode}>
            <div className={styles.centerContent}>
              <div className={styles.icon}><FiLock size={32} /></div>
              <h2 className={styles.stepTitle} style={{ color: colors.textPrimary }}>인증번호 입력</h2>
              <p className={styles.stepDesc} style={{ color: colors.textSecondary }}>{formData.email}로 전송된<br />인증번호를 입력해주세요</p>
            </div>
            <Input label="인증번호" type="text" placeholder="6자리 인증번호 입력" value={formData.verificationCode} onChange={(e) => setFormData({ ...formData, verificationCode: e.target.value })} required />
            <Button type="submit" fullWidth disabled={loading}>{loading ? '확인 중...' : '인증하기'}</Button>
            <div className={styles.resendWrap}>
              <button type="button" onClick={handleSendVerification} className={styles.linkButton} style={{ color: colors.primary }}>인증번호 재전송</button>
            </div>
          </form>
        );

      case 'password-setup':
        return (
          <form onSubmit={handlePasswordSetup}>
            <div className={styles.centerContent}>
              <div className={styles.icon}><FiKey size={32} /></div>
              <h2 className={styles.stepTitle} style={{ color: colors.textPrimary }}>비밀번호 설정</h2>
            </div>
            <div className={styles.passwordRules} style={{ backgroundColor: colors.inputBg }}>
              <p className={styles.rulesTitle} style={{ color: colors.textPrimary }}>비밀번호 조건</p>
              <ul className={styles.rulesList} style={{ color: colors.textSecondary }}>
                <li>8~15자 길이</li>
                <li>영문, 숫자, 특수문자 포함</li>
                <li>연속된 동일 문자 3자 이상 사용 불가</li>
              </ul>
            </div>
            <Input label="비밀번호" type="password" placeholder="비밀번호를 입력하세요" value={formData.password} onChange={(e) => setFormData({ ...formData, password: e.target.value })} required showPasswordToggle />
            <Input label="비밀번호 확인" type="password" placeholder="비밀번호를 다시 입력하세요" value={formData.confirmPassword} onChange={(e) => setFormData({ ...formData, confirmPassword: e.target.value })} required showPasswordToggle />
            <Button type="submit" fullWidth disabled={loading}>{loading ? '가입 중...' : '회원가입 완료'}</Button>
          </form>
        );

      case 'complete':
        return (
          <div className={styles.centerContent}>
            <div className={styles.iconLarge}><BsCheckCircle size={48} color="#10B981" /></div>
            <h2 className={styles.completeTitle} style={{ color: colors.textPrimary }}>환영합니다!</h2>
            <p className={styles.completeDesc} style={{ color: colors.textSecondary }}>회원가입이 완료되었습니다.<br />이제 로그인하여 서비스를 이용하실 수 있습니다.</p>
            <Button fullWidth onClick={() => onViewChange('login')}>로그인하기</Button>
          </div>
        );

      default:
        return null;
    }
  };

  return (
    <div>
      <h1 className={styles.title} style={{ color: colors.textPrimary }}>회원가입</h1>
      <StepIndicator />
      {error && (
        <div className={styles.errorBox} style={{ backgroundColor: '#FEE2E2', borderColor: colors.error, color: '#991B1B' }}>
          {error}
        </div>
      )}
      {renderStepContent()}
      {step === 'user-info' && (
        <div className={styles.footer} style={{ borderTopColor: colors.border, color: colors.textSecondary }}>
          이미 계정이 있으신가요?{' '}
          <button type="button" onClick={() => onViewChange('login')} className={styles.linkButton} style={{ color: colors.primary, fontWeight: 600 }}>로그인</button>
        </div>
      )}
    </div>
  );
};

export default Signup;
