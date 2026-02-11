// ============================================
// LogsPage - Activity Logs
// ============================================

import { useState, useEffect, useMemo } from 'react';
import { FiX } from 'react-icons/fi';
import { AdminLayout } from '../components/AdminLayout';
import { getActivityLogs, getChatHistoryDetail } from '../api/admin.api';
import type { ActivityLog, ChatHistoryDetail } from '../types/admin.types';
import styles from './AdminPages.module.css';

export function LogsPage() {
  const [logs, setLogs] = useState<ActivityLog[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [chatDetail, setChatDetail] = useState<ChatHistoryDetail | null>(null);

  // 필터 상태
  const [startDate, setStartDate] = useState('');
  const [endDate, setEndDate] = useState('');
  const [typeFilter, setTypeFilter] = useState<'all' | 'USER' | 'FLOORPLAN' | 'CHAT'>('all');
  const [searchTerm, setSearchTerm] = useState('');

  // 페이지네이션 상태
  const [currentPage, setCurrentPage] = useState(1);
  const itemsPerPage = 8;

  // 로그 로드
  useEffect(() => {
    const loadLogs = async () => {
      try {
        setIsLoading(true);
        const data = await getActivityLogs();
        setLogs(data);
      } catch (error) {
        console.error('활동 로그 로드 실패:', error);
      } finally {
        setIsLoading(false);
      }
    };
    loadLogs();
  }, []);

  // 필터링된 로그
  const filteredLogs = useMemo(() => {
    const filtered = logs.filter((log) => {
      // 날짜 필터
      if (startDate && log.createdAt < startDate) return false;
      if (endDate && log.createdAt > endDate) return false;

      // 타입 필터
      if (typeFilter !== 'all' && log.type !== typeFilter) return false;

      // 검색어 필터
      if (searchTerm) {
        const search = searchTerm.toLowerCase();
        return (
          log.userName?.toLowerCase().includes(search) ||
          log.userEmail?.toLowerCase().includes(search) ||
          log.action?.toLowerCase().includes(search) ||
          log.details?.toLowerCase().includes(search)
        );
      }

      return true;
    });
    
    // 필터 변경 시 첫 페이지로 이동
    setCurrentPage(1);
    return filtered;
  }, [logs, startDate, endDate, typeFilter, searchTerm]);

  // 현재 페이지의 로그
  const currentLogs = useMemo(() => {
    const startIndex = (currentPage - 1) * itemsPerPage;
    const endIndex = startIndex + itemsPerPage;
    return filteredLogs.slice(startIndex, endIndex);
  }, [filteredLogs, currentPage, itemsPerPage]);

  // 전체 페이지 수
  const totalPages = Math.ceil(filteredLogs.length / itemsPerPage);

  const getTypeLabel = (type: string) => {
    switch (type) {
      case 'USER': return '회원';
      case 'FLOORPLAN': return '도면';
      case 'CHAT': return '챗봇';
      default: return type;
    }
  };

  const getTypeStyle = (type: string) => {
    switch (type) {
      case 'USER': return styles.info;
      case 'FLOORPLAN': return styles.info;
      case 'CHAT': return styles.warning;
      default: return '';
    }
  };

  // 챗봇 대화 상세 보기
  const handleViewChatDetail = async (logId: number) => {
    try {
      const detail = await getChatHistoryDetail(logId);
      setChatDetail(detail);
    } catch (error) {
      console.error('대화 상세 조회 실패:', error);
      alert('대화 내용을 불러올 수 없습니다.');
    }
  };

  return (
    <AdminLayout>
      <div className={styles.page}>
        <div className={styles.pageHeader}>
          <h2 className={styles.pageTitle}>활동 로그</h2>
        </div>

        {/* 필터 */}
        <div className={styles.toolbar}>
          <input
            type="date"
            className={styles.dateInput}
            value={startDate}
            onChange={(e) => setStartDate(e.target.value)}
          />
          <span className={styles.dateSeparator}>~</span>
          <input
            type="date"
            className={styles.dateInput}
            value={endDate}
            onChange={(e) => setEndDate(e.target.value)}
          />
          <select
            className={styles.filterSelect}
            value={typeFilter}
            onChange={(e) => setTypeFilter(e.target.value as any)}
          >
            <option value="all">전체 타입</option>
            <option value="USER">회원가입</option>
            <option value="FLOORPLAN">도면 업로드</option>
            <option value="CHAT">챗봇 대화</option>
          </select>
          <input
            type="text"
            placeholder="사용자 또는 액션 검색..."
            className={styles.searchInput}
            value={searchTerm}
            onChange={(e) => setSearchTerm(e.target.value)}
          />
        </div>

        {/* 로그 테이블 */}
        <div className={styles.tableCard}>
          {isLoading ? (
            <div style={{ textAlign: 'center', padding: '40px' }}>로딩 중...</div>
          ) : filteredLogs.length === 0 ? (
            <div style={{ textAlign: 'center', padding: '40px', color: '#888' }}>
              활동 로그가 없습니다.
            </div>
          ) : (
            <table className={styles.table}>
              <thead>
                <tr>
                  <th>날짜</th>
                  <th>타입</th>
                  <th>사용자</th>
                  <th>액션</th>
                  <th>상세</th>
                  <th>관리</th>
                </tr>
              </thead>
              <tbody>
                {currentLogs.map((log) => (
                  <tr key={`${log.type}-${log.id}`}>
                    <td className={styles.timestamp}>{log.createdAt}</td>
                    <td>
                      <span className={`${styles.logLevel} ${getTypeStyle(log.type)}`}>
                        {getTypeLabel(log.type)}
                      </span>
                    </td>
                    <td>
                      <div>{log.userName}</div>
                      <div style={{ fontSize: '0.85em', color: '#888' }}>{log.userEmail}</div>
                    </td>
                    <td>{log.action}</td>
                    <td className={styles.details}>{log.details}</td>
                    <td>
                      {log.type === 'CHAT' && (
                        <button 
                          className={styles.viewBtn}
                          onClick={() => handleViewChatDetail(log.id)}
                        >
                          상세 보기
                        </button>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>

        {/* 페이지네이션 */}
        <div className={styles.pagination}>
          <span className={styles.pageInfo}>총 {filteredLogs.length}개 로그 (페이지 {currentPage}/{totalPages})</span>
          <div className={styles.pageButtons}>
            <button 
              className={styles.pageBtn} 
              onClick={() => setCurrentPage(prev => Math.max(1, prev - 1))}
              disabled={currentPage === 1}
            >
              이전
            </button>
            {Array.from({ length: totalPages }, (_, i) => i + 1)
              .filter(page => {
                // 현재 페이지 주변 5개만 표시
                return page === 1 || page === totalPages || (page >= currentPage - 2 && page <= currentPage + 2);
              })
              .map((page, index, array) => {
                // ... 표시
                if (index > 0 && page - array[index - 1] > 1) {
                  return [
                    <span key={`ellipsis-${page}`} className={styles.pageEllipsis}>...</span>,
                    <button
                      key={page}
                      className={`${styles.pageBtn} ${currentPage === page ? styles.activePage : ''}`}
                      onClick={() => setCurrentPage(page)}
                    >
                      {page}
                    </button>
                  ];
                }
                return (
                  <button
                    key={page}
                    className={`${styles.pageBtn} ${currentPage === page ? styles.activePage : ''}`}
                    onClick={() => setCurrentPage(page)}
                  >
                    {page}
                  </button>
                );
              })}
            <button 
              className={styles.pageBtn} 
              onClick={() => setCurrentPage(prev => Math.min(totalPages, prev + 1))}
              disabled={currentPage === totalPages}
            >
              다음
            </button>
          </div>
        </div>
      </div>

      {/* 챗봇 대화 상세 모달 */}
      {chatDetail && (
        <div className={styles.modalOverlay} onClick={() => setChatDetail(null)}>
          <div className={styles.modal} onClick={(e) => e.stopPropagation()}>
            <div className={styles.modalHeader}>
              <h3>챗봇 대화 상세</h3>
              <button className={styles.closeBtn} onClick={() => setChatDetail(null)}>
                <FiX />
              </button>
            </div>
            <div className={styles.modalBody}>
              <div className={styles.formGroup}>
                <label>작성일시</label>
                <input type="text" value={new Date(chatDetail.createdAt).toLocaleString('ko-KR')} disabled />
              </div>
              <div className={styles.formGroup}>
                <label>질문</label>
                <textarea 
                  value={chatDetail.question || '질문 없음'} 
                  disabled 
                  rows={5}
                  style={{ 
                    width: '100%', 
                    padding: '10px', 
                    border: '1px solid var(--border-color)',
                    borderRadius: '6px',
                    backgroundColor: 'var(--hover-bg)',
                    color: 'var(--text-primary)',
                    resize: 'none',
                    fontSize: '14px',
                    lineHeight: '0.8'
                  }}
                />
              </div>
              <div className={styles.formGroup}>
                <label>답변</label>
                <textarea 
                  value={chatDetail.answer || '답변 없음'} 
                  disabled 
                  rows={10}
                  style={{ 
                    width: '100%', 
                    padding: '10px', 
                    border: '1px solid var(--border-color)',
                    borderRadius: '6px',
                    backgroundColor: 'var(--hover-bg)',
                    color: 'var(--text-primary)',
                    resize: 'none',
                    fontSize: '14px',
                    lineHeight: '1.5',
                    whiteSpace: 'pre-wrap'
                  }}
                />
              </div>
            </div>
            <div className={styles.modalFooter}>
              <button className={styles.cancelBtn} onClick={() => setChatDetail(null)}>닫기</button>
            </div>
          </div>
        </div>
      )}
    </AdminLayout>
  );
}

