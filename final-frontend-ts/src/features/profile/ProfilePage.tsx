import React, { useState, useEffect, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import { BiChat } from 'react-icons/bi';
import { FiImage, FiCalendar, FiX } from 'react-icons/fi';
import { useTheme } from '@/shared/contexts/ThemeContext';
import { logout as logoutUtil, formatPhoneNumber, parsePhoneNumber } from '@/shared/utils/tokenManager';
import { updateProfile, getCurrentUser } from '@/features/auth/api/auth.api';
import { getChatRooms } from '@/features/chat/api/chat.api';
import { getMyFloorPlans, getFloorPlanDetail, getFloorPlanImage } from './api/profile.api';
import AppSidebar from '@/shared/components/AppSidebar/AppSidebar';
import type { User, MyFloorPlan, FloorPlanDetail } from './types/profile.types';
import type { ChatRoom } from '@/features/chat/types/chat.types';
import styles from './ProfilePage.module.css';

const ProfilePage: React.FC = () => {
  const navigate = useNavigate();
  const { colors } = useTheme();
  const [user, setUser] = useState<User | null>(null);
  const [phoneDisplay, setPhoneDisplay] = useState('');
  const [isEditing, setIsEditing] = useState(false);
  const [chatRooms, setChatRooms] = useState<ChatRoom[]>([]);
  const [floorPlans, setFloorPlans] = useState<MyFloorPlan[]>([]);
  const [modalOpen, setModalOpen] = useState(false);
  const [modalDetail, setModalDetail] = useState<FloorPlanDetail | null>(null);
  const [modalImageUrl, setModalImageUrl] = useState<string | null>(null);
  const [modalLoading, setModalLoading] = useState(false);

  // 현재 날짜 포맷
  const today = new Date();
  const dateString = `${today.getFullYear()}년 ${today.getMonth() + 1}월 ${today.getDate()}일 ${['일', '월', '화', '수', '목', '금', '토'][today.getDay()]}요일`;

  useEffect(() => {
    const fetchData = async () => {
      try {
        const [userInfo, rooms, plans] = await Promise.all([
          getCurrentUser(),
          getChatRooms().catch(() => []),
          getMyFloorPlans().catch(() => []),
        ]);
        setUser({
          id: 0,
          email: userInfo.email,
          name: userInfo.name,
          phonenumber: userInfo.phonenumber,
          role: userInfo.role,
          create_at: userInfo.create_at,
        });
        setPhoneDisplay(formatPhoneNumber(userInfo.phonenumber));
        setChatRooms(rooms);
        setFloorPlans(plans);
      } catch (err) {
        console.error('사용자 정보 불러오기 실패:', err);
        alert('사용자 정보를 불러올 수 없습니다.');
        navigate('/login');
      }
    };
    fetchData();
  }, [navigate]);

  const handleSave = async () => {
    if (!user) return;
    try {
      const phonenumber = parsePhoneNumber(phoneDisplay);
      await updateProfile({ name: user.name, phonenumber });
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

  const handleFloorPlanClick = useCallback(async (planId: number) => {
    setModalLoading(true);
    setModalOpen(true);
    try {
      const [detail, imageUrl] = await Promise.all([
        getFloorPlanDetail(planId),
        getFloorPlanImage(planId),
      ]);
      setModalDetail(detail);
      setModalImageUrl(imageUrl);
    } catch (err) {
      console.error('도면 상세 조회 실패:', err);
      setModalOpen(false);
    } finally {
      setModalLoading(false);
    }
  }, []);

  const handleModalClose = useCallback(() => {
    setModalOpen(false);
    if (modalImageUrl) {
      URL.revokeObjectURL(modalImageUrl);
    }
    setModalDetail(null);
    setModalImageUrl(null);
  }, [modalImageUrl]);

  const formatDate = (dateStr: string) => {
    const d = new Date(dateStr);
    return `${d.getMonth() + 1}/${d.getDate()} ${d.getHours().toString().padStart(2, '0')}:${d.getMinutes().toString().padStart(2, '0')}`;
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
      <AppSidebar />

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

        {/* 그라데이션 배너 (전체 너비) */}
        <div className={styles.gradientBanner} />

        {/* 2열 레이아웃: 좌측 프로필 / 우측 사용 내역 */}
        <div className={styles.twoColumn}>
          {/* 좌측: 프로필 카드 */}
          <div className={styles.leftPanel}>
            <div
              className={styles.card}
              style={{ backgroundColor: '#FFFFFF', boxShadow: '0 4px 20px rgba(0,0,0,0.08)' }}
            >
              <div className={styles.profileHeader}>
                <div className={styles.profileInfo}>
                  <div
                    className={styles.avatarCircle}
                    style={{ backgroundColor: colors.primary }}
                  >
                    {user.name.charAt(0)}
                  </div>
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
                  {isEditing ? '취소' : 'Edit'}
                </button>
              </div>

              <div className={styles.formSection}>
                <div className={styles.formRow}>
                  <div className={styles.formGroup}>
                    <label className={styles.label} style={{ color: colors.textPrimary }}>이름</label>
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
                    <label className={styles.label} style={{ color: colors.textPrimary }}>전화번호</label>
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

                <div className={styles.formRow}>
                  <div className={styles.formGroup}>
                    <label className={styles.label} style={{ color: colors.textPrimary }}>이메일</label>
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
                    <label className={styles.label} style={{ color: colors.textPrimary }}>가입일</label>
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

                <div className={styles.buttonGroup}>
                  {isEditing && (
                    <button onClick={handleSave} className={styles.saveBtn} style={{ backgroundColor: colors.success }}>
                      저장하기
                    </button>
                  )}
                  <button
                    onClick={handleLogout}
                    className={styles.outlineBtn}
                    style={{ border: `1px solid ${colors.border}`, backgroundColor: '#FFFFFF', color: colors.textSecondary }}
                  >
                    로그아웃
                  </button>
                </div>
              </div>
            </div>
          </div>

          {/* 우측: 사용 내역 */}
          <div className={styles.rightPanel}>
            {/* 채팅 내역 */}
            <div
              className={styles.historyCard}
              style={{ backgroundColor: '#FFFFFF', boxShadow: '0 4px 20px rgba(0,0,0,0.08)' }}
            >
              <div className={styles.historyHeader}>
                <h3 className={styles.historyTitle} style={{ color: colors.textPrimary }}>
                  <BiChat size={18} /> 채팅 내역
                </h3>
                <span className={styles.historyCount} style={{ color: colors.textSecondary }}>
                  {chatRooms.length}개
                </span>
              </div>
              <div className={styles.historyList}>
                {chatRooms.length === 0 ? (
                  <p className={styles.emptyText} style={{ color: colors.textSecondary }}>
                    아직 채팅 내역이 없습니다.
                  </p>
                ) : (
                  chatRooms.slice(0, 10).map((room) => (
                    <div
                      key={room.id}
                      className={styles.historyItem}
                      onClick={() => navigate('/main')}
                      style={{ borderBottom: `1px solid ${colors.border}` }}
                    >
                      <div className={styles.historyItemContent}>
                        <span className={styles.historyItemTitle} style={{ color: colors.textPrimary }}>
                          {room.name}
                        </span>
                        <span className={styles.historyItemDate} style={{ color: colors.textSecondary }}>
                          <FiCalendar size={12} /> {formatDate(room.createdAt)}
                        </span>
                      </div>
                    </div>
                  ))
                )}
              </div>
            </div>

            {/* 도면 분석 내역 */}
            <div
              className={styles.historyCard}
              style={{ backgroundColor: '#FFFFFF', boxShadow: '0 4px 20px rgba(0,0,0,0.08)' }}
            >
              <div className={styles.historyHeader}>
                <h3 className={styles.historyTitle} style={{ color: colors.textPrimary }}>
                  <FiImage size={18} /> 도면 분석 내역
                </h3>
                <span className={styles.historyCount} style={{ color: colors.textSecondary }}>
                  {floorPlans.length}개
                </span>
              </div>
              <div className={styles.historyList}>
                {floorPlans.length === 0 ? (
                  <p className={styles.emptyText} style={{ color: colors.textSecondary }}>
                    아직 도면 분석 내역이 없습니다.
                  </p>
                ) : (
                  floorPlans.slice(0, 10).map((plan) => (
                    <div
                      key={plan.id}
                      className={styles.historyItem}
                      onClick={() => handleFloorPlanClick(plan.id)}
                      style={{ borderBottom: `1px solid ${colors.border}` }}
                    >
                      <div className={styles.historyItemContent}>
                        <span className={styles.historyItemTitle} style={{ color: colors.textPrimary }}>
                          {plan.name || '제목 없음'}
                        </span>
                        <span className={styles.historyItemDate} style={{ color: colors.textSecondary }}>
                          <FiCalendar size={12} /> {formatDate(plan.createdAt)}
                        </span>
                      </div>
                    </div>
                  ))
                )}
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* 도면 상세 모달 */}
      {modalOpen && (
        <div className={styles.modalOverlay} onClick={handleModalClose}>
          <div className={styles.modalContent} onClick={(e) => e.stopPropagation()}>
            <button className={styles.modalCloseBtn} onClick={handleModalClose}>
              <FiX size={20} />
            </button>

            {modalLoading ? (
              <div className={styles.modalLoading}>
                <p>불러오는 중...</p>
              </div>
            ) : modalDetail ? (
              <>
                {/* 이미지 영역 */}
                <div className={styles.modalImageSection}>
                  {modalImageUrl ? (
                    <img
                      src={modalImageUrl}
                      alt={modalDetail.name}
                      className={styles.modalImage}
                    />
                  ) : (
                    <div className={styles.modalNoImage}>이미지 없음</div>
                  )}
                </div>

                {/* 정보 영역 */}
                <div className={styles.modalInfoSection}>
                  <h3 className={styles.modalTitle}>{modalDetail.name}</h3>
                  <p className={styles.modalDate}>
                    <FiCalendar size={14} />
                    {new Date(modalDetail.createdAt).toLocaleString('ko-KR')}
                  </p>

                  {modalDetail.assessmentJson && (
                    <div className={styles.modalAssessment}>
                      <h4 className={styles.modalSubtitle}>분석 결과</h4>
                      <pre className={styles.modalJsonContent}>
                        {(() => {
                          try {
                            return JSON.stringify(JSON.parse(modalDetail.assessmentJson), null, 2);
                          } catch {
                            return modalDetail.assessmentJson;
                          }
                        })()}
                      </pre>
                    </div>
                  )}
                </div>
              </>
            ) : null}
          </div>
        </div>
      )}
    </div>
  );
};

export default ProfilePage;
