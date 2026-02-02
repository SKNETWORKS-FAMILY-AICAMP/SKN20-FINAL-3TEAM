import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { FiMessageSquare, FiUser } from 'react-icons/fi';
import { useTheme } from '@/shared/contexts/ThemeContext';
import { logout as logoutUtil, formatPhoneNumber, parsePhoneNumber } from '@/shared/utils/tokenManager';
import { updateProfile, getCurrentUser } from '@/features/auth/api/auth.api';
import type { User } from './types/profile.types';
import styles from './ProfilePage.module.css';

const ProfilePage: React.FC = () => {
  const navigate = useNavigate();
  const { colors } = useTheme();
  const [user, setUser] = useState<User | null>(null);
  const [phoneDisplay, setPhoneDisplay] = useState(''); // 화면 표시/입력용
  const [isEditing, setIsEditing] = useState(false);

  // 현재 날짜 포맷
  const today = new Date();
  const dateString = `${today.getFullYear()}년 ${today.getMonth() + 1}월 ${today.getDate()}일 ${['일', '월', '화', '수', '목', '금', '토'][today.getDay()]}요일`;

  useEffect(() => {
    const fetchUserInfo = async () => {
      try {
        const userInfo = await getCurrentUser();
        setUser({
          id: 0, // API에서 id를 반환하지 않으면 기본값
          email: userInfo.email,
          name: userInfo.name,
          phonenumber: userInfo.phonenumber,
          role: userInfo.role,
          create_at: userInfo.create_at,
        });
        setPhoneDisplay(formatPhoneNumber(userInfo.phonenumber));
      } catch (err) {
        console.error('사용자 정보 불러오기 실패:', err);
        alert('사용자 정보를 불러올 수 없습니다.');
        navigate('/login');
      }
    };
    fetchUserInfo();
  }, [navigate]);

  const handleSave = async () => {
    if (!user) return;

    try {
      const phonenumber = parsePhoneNumber(phoneDisplay);
      await updateProfile({
        name: user.name,
        phonenumber,
      });

      setUser({ ...user, phonenumber });
      alert('프로필이 저장되었습니다.');
      setIsEditing(false);
    } catch (err: any) {
      console.error('프로필 저장 실패:', err);
      alert('프로필 저장에 실패했습니다.');
    }
  };

  const handleLogout = () => {
    if (window.confirm('로그아웃하시겠습니까?')) {
      logoutUtil();
      navigate('/login');
    }
  };

  if (!user) {
    return (
      <div className={styles.loadingContainer} style={{ backgroundColor: colors.background }}>
        <p className={styles.loadingText} style={{ color: colors.textPrimary }}>로딩 중...</p>
      </div>
    );
  }

  return (
    <div className={styles.container} style={{ backgroundColor: colors.background }}>
      {/* 좌측 사이드바 */}
      <div
        className={styles.sidebar}
        style={{ backgroundColor: colors.sidebarBg, borderRight: `1px solid ${colors.border}` }}
      >
        <div onClick={() => navigate('/main')} title="채팅" className={styles.iconBtn}>
          <FiMessageSquare size={20} />
        </div>
        <div
          title="내 계정"
          className={styles.iconBtn}
          style={{
            backgroundColor: '#FEF3C7',
            borderLeft: `3px solid ${colors.primary}`,
          }}
        >
          <FiUser size={20} />
        </div>
      </div>

      {/* 우측 메인 영역 */}
      <div className={styles.mainContent}>
        {/* 상단 헤더 */}
        <div className={styles.header}>
          <h1 className={styles.greeting} style={{ color: colors.textPrimary }}>
            안녕하세요, {user.name} 님.
          </h1>
          <p className={styles.date} style={{ color: colors.textSecondary }}>
            {dateString}
          </p>
        </div>

        {/* 그라데이션 배너 */}
        <div className={styles.gradientBanner} />

        {/* 프로필 카드 */}
        <div
          className={styles.card}
          style={{
            backgroundColor: '#FFFFFF',
            boxShadow: '0 4px 20px rgba(0, 0, 0, 0.08)',
          }}
        >
          {/* 프로필 상단 영역 */}
          <div className={styles.profileHeader}>
            <div className={styles.profileInfo}>
              <div className={styles.userInfo}>
                <h2 className={styles.userName} style={{ color: colors.textPrimary }}>
                  {user.name}
                </h2>
                <p className={styles.userEmail} style={{ color: colors.textSecondary }}>
                  {user.email}
                </p>
              </div>
            </div>
            <button onClick={() => setIsEditing(!isEditing)} className={styles.editBtn}>
              Edit
            </button>
          </div>

          {/* 입력 필드 영역 */}
          <div className={styles.formSection}>
            {/* 2열 배치: 이름, 전화번호 */}
            <div className={styles.formRow}>
              <div className={styles.formGroup}>
                <label className={styles.label} style={{ color: colors.textPrimary }}>
                  이름
                </label>
                <input
                  type="text"
                  value={user.name}
                  onChange={(e) => setUser({ ...user, name: e.target.value })}
                  disabled={!isEditing}
                  className={styles.input}
                  style={{
                    border: `1px solid ${colors.border}`,
                    backgroundColor: isEditing ? '#FFFFFF' : colors.inputBg,
                    color: colors.textPrimary,
                  }}
                />
              </div>
              <div className={styles.formGroup}>
                <label className={styles.label} style={{ color: colors.textPrimary }}>
                  전화번호
                </label>
                <input
                  type="tel"
                  value={phoneDisplay}
                  onChange={(e) => setPhoneDisplay(e.target.value)}
                  placeholder="010-0000-0000"
                  disabled={!isEditing}
                  className={styles.input}
                  style={{
                    border: `1px solid ${colors.border}`,
                    backgroundColor: isEditing ? '#FFFFFF' : colors.inputBg,
                    color: colors.textPrimary,
                  }}
                />
              </div>
            </div>

            {/* 2열 배치: 이메일, 가입일 */}
            <div className={styles.formRow}>
              <div className={styles.formGroup}>
                <label className={styles.label} style={{ color: colors.textPrimary }}>
                  이메일
                </label>
                <input
                  type="email"
                  value={user.email}
                  disabled
                  className={styles.input}
                  style={{
                    border: `1px solid ${colors.border}`,
                    backgroundColor: colors.inputBg,
                    color: colors.textPrimary,
                  }}
                />
              </div>
              <div className={styles.formGroup}>
                <label className={styles.label} style={{ color: colors.textPrimary }}>
                  가입일
                </label>
                <input
                  type="text"
                  value={user.create_at || '-'}
                  disabled
                  className={styles.input}
                  style={{
                    border: `1px solid ${colors.border}`,
                    backgroundColor: colors.inputBg,
                    color: colors.textPrimary,
                  }}
                />
              </div>
            </div>

            {/* 하단 버튼 (오른쪽 정렬) */}
            <div className={styles.buttonGroup}>
              {isEditing && (
                <button
                  onClick={handleSave}
                  className={styles.saveBtn}
                  style={{ backgroundColor: colors.success }}
                >
                  저장하기
                </button>
              )}
              <button
                className={styles.outlineBtn}
                style={{
                  border: `1px solid ${colors.border}`,
                  backgroundColor: '#FFFFFF',
                  color: colors.textSecondary,
                }}
              >
                메뉴얼
              </button>
              <button
                onClick={handleLogout}
                className={styles.outlineBtn}
                style={{
                  border: `1px solid ${colors.border}`,
                  backgroundColor: '#FFFFFF',
                  color: colors.textSecondary,
                }}
              >
                로그아웃
              </button>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};

export default ProfilePage;
