// ============================================
// LogsPage - Activity Logs
// ============================================

import { AdminLayout } from '../components/AdminLayout';
import styles from './AdminPages.module.css';

// 더미 로그 데이터
const dummyLogs = [
  { id: 1, timestamp: '2025-01-23 14:30:25', level: 'info', user: 'user1@example.com', action: '도면 업로드', details: 'floor_plan_001.pdf' },
  { id: 2, timestamp: '2025-01-23 14:28:12', level: 'info', user: 'user2@example.com', action: '로그인', details: 'IP: 192.168.1.100' },
  { id: 3, timestamp: '2025-01-23 14:25:00', level: 'warning', user: 'user3@example.com', action: '분석 실패', details: '지원하지 않는 파일 형식' },
  { id: 4, timestamp: '2025-01-23 14:20:45', level: 'info', user: 'admin@example.com', action: '사용자 수정', details: 'user4 역할 변경' },
  { id: 5, timestamp: '2025-01-23 14:15:30', level: 'error', user: 'system', action: 'API 오류', details: '외부 서비스 연결 실패' },
  { id: 6, timestamp: '2025-01-23 14:10:00', level: 'info', user: 'user1@example.com', action: '분석 완료', details: '3개 방 감지됨' },
];

export function LogsPage() {
  const getLevelStyle = (level: string) => {
    switch (level) {
      case 'info': return styles.info;
      case 'warning': return styles.warning;
      case 'error': return styles.error;
      default: return '';
    }
  };

  return (
    <AdminLayout>
      <div className={styles.page}>
        <div className={styles.pageHeader}>
          <h2 className={styles.pageTitle}>활동 로그</h2>
          <button className={styles.secondaryBtn}>📥 로그 내보내기</button>
        </div>

        {/* 필터 */}
        <div className={styles.toolbar}>
          <input
            type="date"
            className={styles.dateInput}
          />
          <span className={styles.dateSeparator}>~</span>
          <input
            type="date"
            className={styles.dateInput}
          />
          <select className={styles.filterSelect}>
            <option value="all">전체 레벨</option>
            <option value="info">Info</option>
            <option value="warning">Warning</option>
            <option value="error">Error</option>
          </select>
          <input
            type="text"
            placeholder="사용자 또는 액션 검색..."
            className={styles.searchInput}
          />
        </div>

        {/* 로그 테이블 */}
        <div className={styles.tableCard}>
          <table className={styles.table}>
            <thead>
              <tr>
                <th>시간</th>
                <th>레벨</th>
                <th>사용자</th>
                <th>액션</th>
                <th>상세</th>
              </tr>
            </thead>
            <tbody>
              {dummyLogs.map((log) => (
                <tr key={log.id}>
                  <td className={styles.timestamp}>{log.timestamp}</td>
                  <td>
                    <span className={`${styles.logLevel} ${getLevelStyle(log.level)}`}>
                      {log.level.toUpperCase()}
                    </span>
                  </td>
                  <td>{log.user}</td>
                  <td>{log.action}</td>
                  <td className={styles.details}>{log.details}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>

        {/* 페이지네이션 */}
        <div className={styles.pagination}>
          <span className={styles.pageInfo}>총 156개 로그</span>
          <div className={styles.pageButtons}>
            <button className={styles.pageBtn} disabled>이전</button>
            <button className={`${styles.pageBtn} ${styles.active}`}>1</button>
            <button className={styles.pageBtn}>2</button>
            <button className={styles.pageBtn}>3</button>
            <button className={styles.pageBtn}>다음</button>
          </div>
        </div>
      </div>
    </AdminLayout>
  );
}
