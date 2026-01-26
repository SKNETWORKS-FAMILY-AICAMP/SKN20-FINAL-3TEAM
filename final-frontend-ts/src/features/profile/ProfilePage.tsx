import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { FiHome, FiMessageSquare, FiUser } from 'react-icons/fi';
import { useTheme } from '@/shared/contexts';
import { logout as logoutUtil } from '@/shared/utils';
import { updateProfile } from '@/features/auth/api';
import type { User } from './types';
import styles from './ProfilePage.module.css';

const ProfilePage: React.FC = () => {
  const navigate = useNavigate();
  const { colors } = useTheme();
  const [user, setUser] = useState<User | null>(null);
  const [isEditing, setIsEditing] = useState(false);

  // 현재 날짜 포맷
  const today = new Date();
  const dateString = `${today.getFullYear()}년 ${today.getMonth() + 1}월 ${today.getDate()}일 ${['일', '월', '화', '수', '목', '금', '토'][today.getDay()]}요일`;

  useEffect(() => {
    // TODO: 백엔드 연결 시 아래 주석 해제하고 Mock 데이터 삭제
    // const fetchUserInfo = async () => {
    //   try {
    //     const userInfo = await getCurrentUser();
    //     setUser({
    //       id: userInfo.email,
    //       email: userInfo.email,
    //       name: userInfo.name,
    //       position: '',
    //       phone: userInfo.phonenumber.toString(),
    //       profileImage: undefined,
    //     });
    //   } catch (err) {
    //     console.error('사용자 정보 불러오기 실패:', err);
    //     alert('사용자 정보를 불러올 수 없습니다.');
    //     navigate('/login');
    //   }
    // };
    // fetchUserInfo();

    // Mock 데이터 (화면 확인용)
    setUser({
      id: 'test@example.com',
      email: 'ehan3993@gmail.com',
      name: '홍혜원',
      position: '설계팀장',
      phone: '010-1234-5678',
      record: `2026-01-15: 신규 프로젝트 "서울 강남 오피스텔" 도면 분석 완료
2026-01-18: 도면 검색 기능 테스트 진행
2026-01-20: "방 3개, 화장실 2개" 검색으로 유사 도면 5건 발견
2026-01-22: 고객사 미팅 - 도면 수정 요청 접수
2026-01-23: 수정 도면 업로드 및 재분석 진행 중
2026-01-25: 최종 도면 확정 예정
2026-01-28: 프로젝트 완료 보고서 작성 예정`,
    });
  }, [navigate]);

  const handleSave = async () => {
    if (!user) return;

    try {
      await updateProfile({
        name: user.name,
        phonenumber: user.phone,
      });

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
        <div onClick={() => navigate('/')} title="홈" className={styles.iconBtn}>
          <FiHome size={20} />
        </div>
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
            {/* 2열 배치: 이름, 직급 */}
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
                  직급
                </label>
                <input
                  type="text"
                  value={user.position}
                  onChange={(e) => setUser({ ...user, position: e.target.value })}
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

            {/* 2열 배치: 이메일, 전화번호 */}
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
                  전화번호
                </label>
                <input
                  type="tel"
                  value={user.phone}
                  onChange={(e) => setUser({ ...user, phone: e.target.value })}
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

            {/* 기록 필드 (전체 너비) */}
            <div className={styles.formGroup}>
              <label className={styles.label} style={{ color: colors.textPrimary }}>
                기록
              </label>
              <textarea
                rows={6}
                disabled
                value={user.record || ''}
                className={styles.textarea}
                style={{
                  border: `1px solid ${colors.border}`,
                  backgroundColor: colors.inputBg,
                  color: colors.textPrimary,
                }}
              />
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
