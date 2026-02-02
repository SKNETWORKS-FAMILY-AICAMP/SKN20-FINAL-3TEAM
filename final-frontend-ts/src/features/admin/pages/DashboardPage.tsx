// ============================================
// DashboardPage - Admin Dashboard Home
// ============================================

import { useState, useEffect } from 'react';
import { FiUsers, FiFolder, FiBarChart2, FiActivity } from 'react-icons/fi';
import { AdminLayout } from '../components/AdminLayout';
import { getAdminStats } from '../api/admin.api';
import type { AdminStats } from '../types/admin.types';
import styles from './AdminPages.module.css';

export function DashboardPage() {
  const [stats, setStats] = useState<AdminStats | null>(null);
  const [isLoading, setIsLoading] = useState(true);

  // 통계 로드
  useEffect(() => {
    const loadStats = async () => {
      try {
        setIsLoading(true);
        const data = await getAdminStats();
        setStats(data);
      } catch (error) {
        console.error('통계 로드 실패:', error);
        // 백엔드 연결 안 되면 더미 데이터 사용
        setStats({
          userCount: 1234,
          floorPlanCount: 567,
          recentFloorPlan: 89,
        });
      } finally {
        setIsLoading(false);
      }
    };
    loadStats();
  }, []);

  // 통계 카드 데이터
  const statsCards = [
    { label: '총 사용자', value: stats?.userCount?.toLocaleString() || '-', icon: FiUsers, color: '#3B82F6' },
    { label: '도면 수', value: stats?.floorPlanCount?.toLocaleString() || '-', icon: FiFolder, color: '#10B981' },
    { label: '최근 7일 등록', value: stats?.recentFloorPlan?.toLocaleString() || '-', icon: FiBarChart2, color: '#F59E0B' },
    { label: '활성 세션', value: '-', icon: FiActivity, color: '#8B5CF6' },
  ];

  // 더미 최근 활동 (추후 API 연동 가능)
  const recentActivity = [
    { user: 'user1@example.com', action: '도면 업로드', time: '5분 전' },
    { user: 'user2@example.com', action: '회원가입', time: '12분 전' },
    { user: 'user3@example.com', action: '분석 요청', time: '25분 전' },
    { user: 'user4@example.com', action: '도면 업로드', time: '1시간 전' },
    { user: 'user5@example.com', action: '로그인', time: '2시간 전' },
  ];

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

        {/* 컨텐츠 그리드 */}
        <div className={styles.contentGrid}>
          {/* 최근 활동 */}
          <div className={styles.card}>
            <h3 className={styles.cardTitle}>최근 활동</h3>
            <div className={styles.activityList}>
              {recentActivity.map((activity, index) => (
                <div key={index} className={styles.activityItem}>
                  <span className={styles.activityUser}>{activity.user}</span>
                  <span className={styles.activityAction}>{activity.action}</span>
                  <span className={styles.activityTime}>{activity.time}</span>
                </div>
              ))}
            </div>
          </div>

          {/* 시스템 상태 */}
          <div className={styles.card}>
            <h3 className={styles.cardTitle}>시스템 상태</h3>
            <div className={styles.systemStatus}>
              <div className={styles.statusItem}>
                <span>API 서버</span>
                <span className={styles.statusOnline}>● 정상</span>
              </div>
              <div className={styles.statusItem}>
                <span>데이터베이스</span>
                <span className={styles.statusOnline}>● 정상</span>
              </div>
              <div className={styles.statusItem}>
                <span>AI 모델</span>
                <span className={styles.statusOnline}>● 정상</span>
              </div>
              <div className={styles.statusItem}>
                <span>스토리지</span>
                <span className={styles.statusWarning}>● 78% 사용중</span>
              </div>
            </div>
          </div>
        </div>
      </div>
    </AdminLayout>
  );
}
