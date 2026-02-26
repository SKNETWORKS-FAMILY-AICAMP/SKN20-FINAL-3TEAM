// ============================================
// LogsPage - Activity Logs
// ============================================

import { useState, useEffect, useCallback, useRef } from 'react';
import { FiX } from 'react-icons/fi';
import { AdminLayout } from '../components/AdminLayout';
import { getActivityLogs, getChatHistoryDetail } from '../api/admin.api';
import type { ActivityLog, ChatHistoryDetail, ActivityLogParams } from '../types/admin.types';
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

  // 서버 사이드 페이징 상태 (0-based)
  const [currentPage, setCurrentPage] = useState(0);
  const [totalPages, setTotalPages] = useState(0);
  const [totalElements, setTotalElements] = useState(0);
  const itemsPerPage = 8;

  // 디바운스 타이머 ref
  const searchTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  // 초기 로드 완료 여부
  const isInitialMount = useRef(true);

  // 로그 로드 (서버 사이드 페이징 + 필터링)
  const loadLogs = useCallback(async (page: number = 0) => {
    try {
      setIsLoading(true);
      const params: ActivityLogParams = {
        page,
        size: itemsPerPage,
      };
      if (startDate) params.startDate = startDate;
      if (endDate) params.endDate = endDate;
      if (typeFilter !== 'all') params.type = typeFilter;
      if (searchTerm.trim()) params.search = searchTerm.trim();

      const data = await getActivityLogs(params);
      setLogs(data.content);
      setCurrentPage(data.currentPage);
      setTotalPages(data.totalPages);
      setTotalElements(data.totalElements);
    } catch (error) {
      console.error('활동 로그 로드 실패:', error);
    } finally {
      setIsLoading(false);
    }
  }, [startDate, endDate, typeFilter, searchTerm]);

  // 초기 로드
  useEffect(() => {
    loadLogs(0);
  }, []);

  // 날짜/타입 필터 변경 시 첫 페이지로 재로드 (초기 로드 제외)
  useEffect(() => {
    if (isInitialMount.current) {
      isInitialMount.current = false;
      return;
    }
    loadLogs(0);
  }, [startDate, endDate, typeFilter]);

  // 검색어 디바운스 (300ms)
  useEffect(() => {
    if (isInitialMount.current) return;

    if (searchTimerRef.current) {
      clearTimeout(searchTimerRef.current);
    }
    searchTimerRef.current = setTimeout(() => {
      loadLogs(0);
    }, 300);

    return () => {
      if (searchTimerRef.current) {
        clearTimeout(searchTimerRef.current);
      }
    };
  }, [searchTerm]);

  // 페이지 변경
  const handlePageChange = (newPage: number) => {
    loadLogs(newPage);
  };

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

  // 표시용 페이지 번호 (1-based)
  const displayPage = currentPage + 1;

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
          ) : totalElements === 0 ? (
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
                {logs.map((log) => (
                  <tr key={`${log.type}-${log.id}`}>
                    <td className={styles.timestamp}>{(() => { const d = new Date(log.createdAt); return `${d.getFullYear()}.${(d.getMonth()+1).toString().padStart(2,'0')}.${d.getDate().toString().padStart(2,'0')} ${d.getHours().toString().padStart(2,'0')}:${d.getMinutes().toString().padStart(2,'0')}`; })()}</td>
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
          <span className={styles.pageInfo}>총 {totalElements}개 로그 (페이지 {displayPage}/{totalPages || 1})</span>
          <div className={styles.pageButtons}>
            <button
              className={styles.pageBtn}
              onClick={() => handlePageChange(currentPage - 1)}
              disabled={currentPage === 0}
            >
              이전
            </button>
            {Array.from({ length: totalPages }, (_, i) => i + 1)
              .filter(page => {
                // 현재 페이지 주변 5개만 표시
                return page === 1 || page === totalPages || (page >= displayPage - 2 && page <= displayPage + 2);
              })
              .map((page, index, array) => {
                // ... 표시
                if (index > 0 && page - array[index - 1] > 1) {
                  return [
                    <span key={`ellipsis-${page}`} className={styles.pageEllipsis}>...</span>,
                    <button
                      key={page}
                      className={`${styles.pageBtn} ${displayPage === page ? styles.activePage : ''}`}
                      onClick={() => handlePageChange(page - 1)}
                    >
                      {page}
                    </button>
                  ];
                }
                return (
                  <button
                    key={page}
                    className={`${styles.pageBtn} ${displayPage === page ? styles.activePage : ''}`}
                    onClick={() => handlePageChange(page - 1)}
                  >
                    {page}
                  </button>
                );
              })}
            <button
              className={styles.pageBtn}
              onClick={() => handlePageChange(currentPage + 1)}
              disabled={currentPage >= totalPages - 1}
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
                <input type="text" value={(() => { const d = new Date(chatDetail.createdAt); return `${d.getFullYear()}.${(d.getMonth()+1).toString().padStart(2,'0')}.${d.getDate().toString().padStart(2,'0')} ${d.getHours().toString().padStart(2,'0')}:${d.getMinutes().toString().padStart(2,'0')}`; })()} disabled />
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
