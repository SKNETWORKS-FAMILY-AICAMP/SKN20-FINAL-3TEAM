// ============================================
// DashboardPage - Admin Dashboard Home
// ============================================

import { useState, useEffect } from 'react';
import { FiUsers, FiFolder, FiBarChart2, FiMessageSquare, FiTrendingUp, FiServer } from 'react-icons/fi';
import { AdminLayout } from '../components/AdminLayout';
import { getAdminStats, getActivityLogs } from '../api/admin.api';
import type { AdminStats, ActivityLog } from '../types/admin.types';
import styles from './AdminPages.module.css';

export function DashboardPage() {
  const [stats, setStats] = useState<AdminStats | null>(null);
  const [recentLogs, setRecentLogs] = useState<ActivityLog[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [currentTime, setCurrentTime] = useState(new Date());

  // 통계 및 최근 활동 로드
  useEffect(() => {
    const loadData = async () => {
      try {
        setIsLoading(true);
        const [statsData, logsData] = await Promise.all([
          getAdminStats(),
          getActivityLogs()
        ]);
        setStats(statsData);
        setRecentLogs(logsData.slice(0, 5)); // 최근 5개만
      } catch (error) {
        console.error('데이터 로드 실패:', error);
      } finally {
        setIsLoading(false);
      }
    };
    loadData();
  }, []);

  // 시스템 시간 업데이트
  useEffect(() => {
    const timer = setInterval(() => {
      setCurrentTime(new Date());
    }, 1000);
    return () => clearInterval(timer);
  }, []);

  // 통계 카드 데이터
  const statsCards = [
    { label: '총 사용자', value: stats?.userCount?.toLocaleString() || '-', icon: FiUsers, color: '#3B82F6' },
    { label: '도면 수', value: stats?.floorPlanCount?.toLocaleString() || '-', icon: FiFolder, color: '#10B981' },
    { label: '최근 7일 등록', value: stats?.recentFloorPlan?.toLocaleString() || '-', icon: FiBarChart2, color: '#F59E0B' },
    { label: '총 채팅', value: stats?.totalChatCount?.toLocaleString() || '-', icon: FiMessageSquare, color: '#8B5CF6' },
    { label: '최근 7일 채팅', value: stats?.recentChatCount?.toLocaleString() || '-', icon: FiTrendingUp, color: '#EC4899' },
    { label: '채팅방 수', value: stats?.chatRoomCount?.toLocaleString() || '-', icon: FiMessageSquare, color: '#06B6D4' },
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

        {/* 하단 섹션: 최근 활동 & 시스템 상태 */}
        <div className={styles.dashboardBottom}>
          {/* 최근 활동 로그 */}
          <div className={styles.recentActivity}>
            <h3 className={styles.sectionTitle}>최근 활동</h3>
            {isLoading ? (
              <div style={{ textAlign: 'center', padding: '2rem', color: '#9CA3AF' }}>
                로딩 중...
              </div>
            ) : recentLogs.length === 0 ? (
              <div style={{ textAlign: 'center', padding: '2rem', color: '#9CA3AF' }}>
                활동 내역이 없습니다
              </div>
            ) : (
              <div className={styles.activityList}>
                {recentLogs.map((log) => {
                  // 활동 타입별 스타일 설정
                  const getActivityStyle = (type: string) => {
                    switch(type) {
                      case 'USER':
                        return { bg: '#EDE9FE', color: '#7C3AED', icon: <FiUsers size={16} /> };
                      case 'CHATROOM':
                      case 'CHAT':
                        return { bg: '#EEF2FF', color: '#6366F1', icon: <FiMessageSquare size={16} /> };
                      case 'FLOORPLAN':
                      default:
                        return { bg: '#F0FDF4', color: '#10B981', icon: <FiFolder size={16} /> };
                    }
                  };
                  const style = getActivityStyle(log.type);

                  return (
                    <div key={log.id} className={styles.activityItem}>
                      <div className={styles.activityIcon} style={{ 
                        backgroundColor: style.bg,
                        color: style.color
                      }}>
                        {style.icon}
                      </div>
                      <div className={styles.activityContent}>
                        <div className={styles.activityUser}>{log.userName || '익명'}</div>
                        <div className={styles.activityMessage}>
                          {log.action} - {log.details.length > 50 ? log.details.substring(0, 50) + '...' : log.details}
                        </div>
                        <div className={styles.activityTime}>
                          {new Date(log.createdAt).toLocaleString('ko-KR')}
                        </div>
                      </div>
                    </div>
                  );
                })}
              </div>
            )}
          </div>

          {/* 시스템 상태 */}
          <div className={styles.systemStatus}>
            <h3 className={styles.sectionTitle}>시스템 상태</h3>
            <div className={styles.statusList}>
              <div className={styles.statusItem}>
                <div className={styles.statusIndicator} style={{ backgroundColor: '#10B981' }} />
                <div className={styles.statusInfo}>
                  <div className={styles.statusLabel}>API 서버</div>
                  <div className={styles.statusValue}>정상 작동</div>
                </div>
                <FiServer size={20} color="#10B981" />
              </div>
              <div className={styles.statusItem}>
                <div className={styles.statusIndicator} style={{ backgroundColor: '#10B981' }} />
                <div className={styles.statusInfo}>
                  <div className={styles.statusLabel}>데이터베이스</div>
                  <div className={styles.statusValue}>연결됨</div>
                </div>
                <FiServer size={20} color="#10B981" />
              </div>
              <div className={styles.statusItem}>
                <div className={styles.statusIndicator} style={{ backgroundColor: '#10B981' }} />
                <div className={styles.statusInfo}>
                  <div className={styles.statusLabel}>시스템 시간</div>
                  <div className={styles.statusValue}>
                    {currentTime.toLocaleString('ko-KR')}
                  </div>
                </div>
                <FiBarChart2 size={20} color="#6366F1" />
              </div>
              <div className={styles.statusItem}>
                <div className={styles.statusIndicator} style={{ backgroundColor: '#F59E0B' }} />
                <div className={styles.statusInfo}>
                  <div className={styles.statusLabel}>활동 추이</div>
                  <div className={styles.statusValue}>
                    {stats ? '최근 7일: ' + (stats.recentFloorPlan + stats.recentChatCount) + '건' : '계산 중...'}
                  </div>
                </div>
                <FiTrendingUp size={20} color="#F59E0B" />
              </div>
            </div>
          </div>
        </div>

      </div>
    </AdminLayout>
  );
}
