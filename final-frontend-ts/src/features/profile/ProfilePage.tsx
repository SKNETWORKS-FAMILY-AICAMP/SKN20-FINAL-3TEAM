import React, { useState, useEffect, useCallback, useRef } from 'react';
import { useNavigate } from 'react-router-dom';
import { BiChat } from 'react-icons/bi';
import { FiImage, FiCalendar, FiX, FiMail, FiLock } from 'react-icons/fi';
import { useTheme } from '@/shared/contexts/ThemeContext';
import { logout as logoutUtil } from '@/shared/utils/tokenManager';
import { updateProfile, getCurrentUser, changePassword, sendVerificationMail, verifyMailCode } from '@/features/auth/api/auth.api';
import { getChatRooms } from '@/features/chat/api/chat.api';
import { getMyFloorPlans, getFloorPlanDetail } from './api/profile.api';
import AppSidebar from '@/shared/components/AppSidebar/AppSidebar';
import type { User, MyFloorPlan, FloorPlanDetail } from './types/profile.types';
import type { ChatRoom } from '@/features/chat/types/chat.types';
import styles from './ProfilePage.module.css';

const ProfilePage: React.FC = () => {
  const navigate = useNavigate();
  const { colors } = useTheme();
  const [user, setUser] = useState<User | null>(null);
  const [isEditing, setIsEditing] = useState(false);
  const [chatRooms, setChatRooms] = useState<ChatRoom[]>([]);
  const [floorPlans, setFloorPlans] = useState<MyFloorPlan[]>([]);
  const [modalOpen, setModalOpen] = useState(false);
  const [modalDetail, setModalDetail] = useState<FloorPlanDetail | null>(null);
  const [modalImageUrl, setModalImageUrl] = useState<string | null>(null);
  const [modalLoading, setModalLoading] = useState(false);
  // 비밀번호 변경 4단계: 'idle' → 'verify' → 'code' → 'newpw'
  const [pwStep, setPwStep] = useState<'idle' | 'verify' | 'code' | 'newpw'>('idle');
  const [pwForm, setPwForm] = useState({ newPassword: '', confirmPassword: '' });
  const [verifyCode, setVerifyCode] = useState('');
  const [pwError, setPwError] = useState('');
  const [pwSuccess, setPwSuccess] = useState('');
  const [pwLoading, setPwLoading] = useState(false);
  const [verifyTimer, setVerifyTimer] = useState(0);
  const timerRef = useRef<ReturnType<typeof setInterval> | null>(null);

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
      await updateProfile({ name: user.name, phonenumber: user.phonenumber });
      setUser({ ...user });
      alert('프로필이 저장되었습니다.');
      setIsEditing(false);
    } catch (err: any) {
      console.error('프로필 저장 실패:', err);
      alert('프로필 저장에 실패했습니다.');
    }
  };

  const startTimer = (seconds: number) => {
    if (timerRef.current) clearInterval(timerRef.current);
    setVerifyTimer(seconds);
    timerRef.current = setInterval(() => {
      setVerifyTimer(prev => {
        if (prev <= 1) {
          clearInterval(timerRef.current!);
          timerRef.current = null;
          return 0;
        }
        return prev - 1;
      });
    }, 1000);
  };

  const formatTimer = (sec: number) => {
    const m = Math.floor(sec / 60);
    const s = sec % 60;
    return `${m}:${s.toString().padStart(2, '0')}`;
  };

  // Step 1: 변경하기 클릭 → verify 단계로 이동
  const handleStartPwChange = () => {
    setPwError('');
    setPwSuccess('');
    setPwStep('verify');
  };

  // Step 2: 이메일 인증 버튼 클릭 → 인증 메일 발송
  const handleSendVerification = async () => {
    setPwError('');
    setPwLoading(true);
    try {
      await sendVerificationMail({ email: user!.email });
      setPwStep('code');
      startTimer(300);
    } catch (err: any) {
      setPwError('인증 메일 발송에 실패했습니다.');
    } finally {
      setPwLoading(false);
    }
  };

  // Step 3: 인증번호 확인
  const handleVerifyCode = async () => {
    setPwError('');
    if (!verifyCode || verifyCode.length !== 6) {
      setPwError('6자리 인증번호를 입력해주세요.');
      return;
    }
    setPwLoading(true);
    try {
      await verifyMailCode({ mail: user!.email, userNumber: parseInt(verifyCode) });
      if (timerRef.current) clearInterval(timerRef.current);
      setPwStep('newpw');
    } catch (err: any) {
      setPwError('인증번호가 올바르지 않습니다.');
    } finally {
      setPwLoading(false);
    }
  };

  // Step 3: 새 비밀번호 저장
  const handleChangePassword = async () => {
    setPwError('');
    if (!pwForm.newPassword || !pwForm.confirmPassword) {
      setPwError('모든 항목을 입력해주세요.');
      return;
    }
    if (pwForm.newPassword.length < 8) {
      setPwError('비밀번호는 8자 이상이어야 합니다.');
      return;
    }
    if (pwForm.newPassword !== pwForm.confirmPassword) {
      setPwError('비밀번호가 일치하지 않습니다.');
      return;
    }
    setPwLoading(true);
    try {
      await changePassword({ email: user!.email, newPassword: pwForm.newPassword });
      setPwSuccess('비밀번호가 변경되었습니다.');
      setPwForm({ newPassword: '', confirmPassword: '' });
      setVerifyCode('');
      setPwStep('idle');
    } catch (err: any) {
      setPwError(err.response?.data?.message || '비밀번호 변경에 실패했습니다.');
    } finally {
      setPwLoading(false);
    }
  };

  const handleCancelPwChange = () => {
    if (timerRef.current) clearInterval(timerRef.current);
    setPwStep('idle');
    setPwForm({ newPassword: '', confirmPassword: '' });
    setVerifyCode('');
    setPwError('');
    setPwSuccess('');
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
      const detail = await getFloorPlanDetail(planId);
      setModalDetail(detail);
      setModalImageUrl(detail.imageUrl);
    } catch (err) {
      console.error('도면 상세 조회 실패:', err);
      setModalOpen(false);
    } finally {
      setModalLoading(false);
    }
  }, []);

  const handleModalClose = useCallback(() => {
    setModalOpen(false);
    setModalDetail(null);
    setModalImageUrl(null);
  }, []);

  const formatDate = (dateStr: string) => {
    const d = new Date(dateStr);
    return `${d.getFullYear()}.${(d.getMonth() + 1).toString().padStart(2, '0')}.${d.getDate().toString().padStart(2, '0')} ${d.getHours().toString().padStart(2, '0')}:${d.getMinutes().toString().padStart(2, '0')}`;
  };

  const formatDateOnly = (dateStr: string) => {
    const d = new Date(dateStr);
    return `${d.getFullYear()}.${(d.getMonth() + 1).toString().padStart(2, '0')}.${d.getDate().toString().padStart(2, '0')}`;
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
                      <FiMail size={13} style={{ marginRight: '4px', verticalAlign: 'middle' }} />
                      {user.email}
                    </p>
                  </div>
                </div>
                <button onClick={() => setIsEditing(!isEditing)} className={styles.editBtn}>
                  {isEditing ? '취소' : 'Edit'}
                </button>
              </div>

              <div className={styles.formSection}>
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
                    value={user.create_at ? formatDateOnly(user.create_at) : '-'}
                    disabled
                    className={styles.input}
                    style={{
                      border: `1px solid ${colors.border}`,
                      backgroundColor: colors.inputBg,
                      color: colors.textPrimary,
                    }}
                  />
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

            {/* 비밀번호 변경 */}
            <div
              className={styles.card}
              style={{ backgroundColor: '#FFFFFF', boxShadow: '0 4px 20px rgba(0,0,0,0.08)' }}
            >
              <div className={styles.pwHeader}>
                <FiLock size={18} />
                <h3 className={styles.pwTitle} style={{ color: colors.textPrimary }}>비밀번호 변경</h3>
              </div>

              {/* Step 1: idle - 비밀번호 변경하기 풀사이즈 버튼 */}
              {pwStep === 'idle' && (
                <div className={styles.formSection}>
                  <p className={styles.pwDesc} style={{ color: colors.textSecondary }}>
                    이메일 인증 후 비밀번호를 변경할 수 있습니다.
                  </p>
                  {pwSuccess && (
                    <p className={styles.pwMessage} style={{ color: '#16A34A' }}>{pwSuccess}</p>
                  )}
                  <button
                    onClick={handleStartPwChange}
                    className={styles.pwFullBtn}
                    style={{ backgroundColor: colors.primary }}
                  >
                    비밀번호 변경하기
                  </button>
                </div>
              )}

              {/* Step 2: verify - 이메일 인증 발송 버튼 */}
              {pwStep === 'verify' && (
                <div className={styles.formSection}>
                  <p className={styles.pwDesc} style={{ color: colors.textSecondary }}>
                    <strong>{user.email}</strong>로 인증번호를 발송합니다.
                  </p>
                  {pwError && (
                    <p className={styles.pwMessage} style={{ color: '#DC2626' }}>{pwError}</p>
                  )}
                  <div className={styles.buttonGroup}>
                    <button
                      onClick={handleCancelPwChange}
                      className={styles.outlineBtn}
                      style={{ border: `1px solid ${colors.border}`, backgroundColor: '#FFFFFF', color: colors.textSecondary }}
                    >
                      취소
                    </button>
                    <button
                      onClick={handleSendVerification}
                      className={styles.saveBtn}
                      style={{ backgroundColor: colors.primary }}
                      disabled={pwLoading}
                    >
                      {pwLoading ? '발송 중...' : '이메일 인증'}
                    </button>
                  </div>
                </div>
              )}

              {/* Step 3: code - 인증번호 입력 */}
              {pwStep === 'code' && (
                <div className={styles.formSection}>
                  <div className={styles.verifyRow}>
                    <input
                      type="text"
                      placeholder="인증번호 6자리"
                      value={verifyCode}
                      onChange={(e) => setVerifyCode(e.target.value.replace(/\D/g, '').slice(0, 6))}
                      className={styles.input}
                      style={{
                        border: `1px solid ${colors.border}`,
                        backgroundColor: '#FFFFFF',
                        color: colors.textPrimary,
                        flex: 1,
                      }}
                      maxLength={6}
                    />
                    {verifyTimer > 0 && (
                      <span className={styles.timerText} style={{ color: verifyTimer <= 60 ? '#DC2626' : colors.textSecondary }}>
                        {formatTimer(verifyTimer)}
                      </span>
                    )}
                  </div>
                  {pwError && (
                    <p className={styles.pwMessage} style={{ color: '#DC2626' }}>{pwError}</p>
                  )}
                  <div className={styles.buttonGroup}>
                    <button
                      onClick={handleCancelPwChange}
                      className={styles.outlineBtn}
                      style={{ border: `1px solid ${colors.border}`, backgroundColor: '#FFFFFF', color: colors.textSecondary }}
                    >
                      취소
                    </button>
                    <button
                      onClick={handleVerifyCode}
                      className={styles.saveBtn}
                      style={{ backgroundColor: colors.primary }}
                      disabled={pwLoading || verifyTimer === 0}
                    >
                      {pwLoading ? '확인 중...' : '인증 확인'}
                    </button>
                  </div>
                </div>
              )}

              {/* Step 3: newpw - 새 비밀번호 입력 */}
              {pwStep === 'newpw' && (
                <div className={styles.formSection}>
                  <div className={styles.formRow}>
                    <div className={styles.formGroup}>
                      <label className={styles.label} style={{ color: colors.textPrimary }}>새 비밀번호</label>
                      <input
                        type="password"
                        placeholder="영문자, 숫자, 특수문자 포함 8자 이상"
                        value={pwForm.newPassword}
                        onChange={(e) => setPwForm({ ...pwForm, newPassword: e.target.value })}
                        className={styles.input}
                        style={{
                          border: `1px solid ${colors.border}`,
                          backgroundColor: '#FFFFFF',
                          color: colors.textPrimary,
                        }}
                      />
                    </div>
                    <div className={styles.formGroup}>
                      <label className={styles.label} style={{ color: colors.textPrimary }}>비밀번호 확인</label>
                      <input
                        type="password"
                        placeholder="비밀번호 재입력"
                        value={pwForm.confirmPassword}
                        onChange={(e) => setPwForm({ ...pwForm, confirmPassword: e.target.value })}
                        className={styles.input}
                        style={{
                          border: `1px solid ${colors.border}`,
                          backgroundColor: '#FFFFFF',
                          color: colors.textPrimary,
                        }}
                      />
                    </div>
                  </div>
                  {pwError && (
                    <p className={styles.pwMessage} style={{ color: '#DC2626' }}>{pwError}</p>
                  )}
                  <div className={styles.buttonGroup}>
                    <button
                      onClick={handleCancelPwChange}
                      className={styles.outlineBtn}
                      style={{ border: `1px solid ${colors.border}`, backgroundColor: '#FFFFFF', color: colors.textSecondary }}
                    >
                      취소
                    </button>
                    <button
                      onClick={handleChangePassword}
                      className={styles.saveBtn}
                      style={{ backgroundColor: colors.primary }}
                      disabled={pwLoading}
                    >
                      {pwLoading ? '변경 중...' : '비밀번호 변경'}
                    </button>
                  </div>
                </div>
              )}
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
                      onClick={() => navigate(`/main?roomId=${room.id}`)}
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
                    {formatDate(modalDetail.createdAt)}
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
