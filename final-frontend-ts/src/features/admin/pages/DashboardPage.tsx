// ============================================
// DashboardPage - Admin Dashboard Home
// ============================================

import { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { FiUsers, FiFolder, FiBarChart2, FiMessageSquare, FiTrendingUp, FiFileText, FiList } from 'react-icons/fi';
import { AdminLayout } from '../components/AdminLayout';
import { getAdminStats, getFloorPlans } from '../api/admin.api';
import type { AdminStats, AdminFloorPlan } from '../types/admin.types';
import styles from './AdminPages.module.css';

export function DashboardPage() {
  const navigate = useNavigate();
  const [stats, setStats] = useState<AdminStats | null>(null);
  const [recentPlans, setRecentPlans] = useState<AdminFloorPlan[]>([]);
  const [isLoading, setIsLoading] = useState(true);

  useEffect(() => {
    const loadData = async () => {
      try {
        setIsLoading(true);
        const [statsData, plansData] = await Promise.all([
          getAdminStats(),
          getFloorPlans(0, 6)
        ]);
        setStats(statsData);
        setRecentPlans(plansData.content);
      } catch (error) {
        console.error('데이터 로드 실패:', error);
      } finally {
        setIsLoading(false);
      }
    };
    loadData();
  }, []);

  const statsCards = [
    { label: '총 사용자', value: stats?.userCount?.toLocaleString() || '-', icon: FiUsers, color: '#3B82F6' },
    { label: '도면 자산', value: stats?.floorPlanCount?.toLocaleString() || '-', icon: FiFolder, color: '#10B981' },
    { label: '최근 7일 등록', value: stats?.recentFloorPlan?.toLocaleString() || '-', icon: FiBarChart2, color: '#F59E0B' },
    { label: '총 채팅', value: stats?.totalChatCount?.toLocaleString() || '-', icon: FiMessageSquare, color: '#8B5CF6' },
    { label: '최근 7일 채팅', value: stats?.recentChatCount?.toLocaleString() || '-', icon: FiTrendingUp, color: '#EC4899' },
    { label: '채팅방 수', value: stats?.chatRoomCount?.toLocaleString() || '-', icon: FiMessageSquare, color: '#06B6D4' },
  ];

  const formatDate = (dateStr?: string) => {
    if (!dateStr) return '-';
    const date = new Date(dateStr);
    const now = new Date();
    const diffMs = now.getTime() - date.getTime();
    const diffDays = Math.floor(diffMs / (1000 * 60 * 60 * 24));
    if (diffDays === 0) return '오늘';
    if (diffDays === 1) return '어제';
    if (diffDays < 7) return `${diffDays}일 전`;
    return date.toLocaleDateString('ko-KR');
  };

  return (
    <AdminLayout>
      <div className={styles.page}>
        <h2 className={styles.pageTitle}>대시보드</h2>

        {/* 통계 카드 */}
        <div className={styles.statsGrid}>
          {statsCards.map((stat) => (
            <div key={stat.label} className={styles.statCard}>
              <div className={styles.statIcon} style={{ backgroundColor: `${stat.color}15`, color: stat.color }}>
                <stat.icon size={24} />
              </div>
              <div className={styles.statInfo}>
                <span className={styles.statValue}>
                  {isLoading ? '...' : stat.value}
                </span>
                <span className={styles.statLabel}>{stat.label}</span>
              </div>
            </div>
          ))}
        </div>

        {/* 하단 섹션: 최근 등록 도면 & 빠른 이동 */}
        <div className={styles.dashboardBottom}>
          {/* 최근 등록 도면 갤러리 */}
          <div className={styles.recentActivity}>
            <h3 className={styles.sectionTitle}>최근 등록 도면</h3>
            {isLoading ? (
              <div style={{ textAlign: 'center', padding: '2rem', color: '#9CA3AF' }}>
                로딩 중...
              </div>
            ) : recentPlans.length === 0 ? (
              <div style={{ textAlign: 'center', padding: '2rem', color: '#9CA3AF' }}>
                등록된 도면이 없습니다
              </div>
            ) : (
              <div className={styles.recentPlanGrid}>
                {recentPlans.map((plan) => (
                  <div
                    key={plan.id}
                    className={styles.recentPlanCard}
                    onClick={() => navigate(`/admin/floor-plans?search=${encodeURIComponent(plan.name || '')}`)}
                  >
                    <div className={styles.recentPlanImage}>
                      {plan.imageUrl ? (
                        <img
                          src={plan.imageUrl}
                          alt={plan.name}
                          onError={(e) => {
                            (e.target as HTMLImageElement).style.display = 'none';
                            (e.target as HTMLImageElement).parentElement!.classList.add(styles.recentPlanNoImage);
                          }}
                        />
                      ) : (
                        <div className={styles.recentPlanNoImage}>
                          <FiFolder size={20} />
                        </div>
                      )}
                    </div>
                    <div className={styles.recentPlanInfo}>
                      <span className={styles.recentPlanName}>{plan.name || '제목 없음'}</span>
                      <span className={styles.recentPlanMeta}>{plan.user?.email || '-'}</span>
                      <span className={styles.recentPlanMeta}>{formatDate(plan.createdAt)}</span>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>

          {/* 빠른 이동 + 이번 주 요약 */}
          <div className={styles.systemStatus}>
            <h3 className={styles.sectionTitle}>빠른 이동</h3>
            <div className={styles.quickLinkList}>
              <button className={styles.quickLinkBtn} onClick={() => navigate('/admin/floor-plans')}>
                <div className={styles.quickLinkIcon} style={{ backgroundColor: '#EFF6FF', color: '#3B82F6' }}>
                  <FiFileText size={20} />
                </div>
                <div className={styles.quickLinkText}>
                  <span className={styles.quickLinkLabel}>도면 DB 관리</span>
                  <span className={styles.quickLinkDesc}>도면 자산 검색, 상세보기, 삭제</span>
                </div>
              </button>
              <button className={styles.quickLinkBtn} onClick={() => navigate('/admin/logs')}>
                <div className={styles.quickLinkIcon} style={{ backgroundColor: '#F5F3FF', color: '#7C3AED' }}>
                  <FiList size={20} />
                </div>
                <div className={styles.quickLinkText}>
                  <span className={styles.quickLinkLabel}>활동 로그</span>
                  <span className={styles.quickLinkDesc}>회원가입, 도면 업로드, 챗봇 내역</span>
                </div>
              </button>
            </div>

            {/* 이번 주 요약 */}
            {stats && (
              <div className={styles.weeklySummary}>
                <h4 className={styles.weeklySummaryTitle}>이번 주 요약</h4>
                <div className={styles.weeklySummaryItem}>
                  <span>신규 도면</span>
                  <strong>{stats.recentFloorPlan}건</strong>
                </div>
                <div className={styles.weeklySummaryItem}>
                  <span>챗봇 질문</span>
                  <strong>{stats.recentChatCount}건</strong>
                </div>
                <div className={styles.weeklySummaryItem}>
                  <span>총 도면 자산</span>
                  <strong>{stats.floorPlanCount}건</strong>
                </div>
              </div>
            )}
          </div>
        </div>
      </div>
    </AdminLayout>
  );
}
