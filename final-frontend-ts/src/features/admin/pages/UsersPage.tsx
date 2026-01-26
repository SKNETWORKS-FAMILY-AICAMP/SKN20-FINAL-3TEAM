// ============================================
// UsersPage - User Management
// ============================================

import { useState, useEffect, useCallback } from 'react';
import { FiEdit2, FiTrash2, FiX, FiEye, FiMessageSquare } from 'react-icons/fi';
import { AdminLayout } from '../components/AdminLayout';
import { getUsers, searchUsers, editUser, deleteEntities, getUserDetail, getUserHistory } from '../api';
import type { AdminUser, AdminChatRoom } from '../types';
import styles from './AdminPages.module.css';

export function UsersPage() {
  const [users, setUsers] = useState<AdminUser[]>([]);
  const [searchTerm, setSearchTerm] = useState('');
  const [isLoading, setIsLoading] = useState(true);
  const [selectedIds, setSelectedIds] = useState<number[]>([]);

  // 수정 모달 상태
  const [editingUser, setEditingUser] = useState<AdminUser | null>(null);
  const [editForm, setEditForm] = useState({ name: '', phone: '', role: '' });

  // 상세 보기 모달 상태
  const [detailUser, setDetailUser] = useState<AdminUser | null>(null);

  // 채팅 기록 모달 상태
  const [historyUser, setHistoryUser] = useState<AdminUser | null>(null);
  const [chatHistory, setChatHistory] = useState<AdminChatRoom[]>([]);
  const [isHistoryLoading, setIsHistoryLoading] = useState(false);

  // 유저 목록 로드
  const loadUsers = useCallback(async () => {
    try {
      setIsLoading(true);
      const data = await getUsers();
      setUsers(data);
    } catch (error) {
      console.error('유저 목록 로드 실패:', error);
      // 백엔드 연결 안 되면 더미 데이터
      setUsers([
        { id: 1, email: 'admin@example.com', name: '관리자', phonenumber: 1012345678, role: 'admin', created_at: '2025-01-01', update_at: '2025-01-01' },
        { id: 2, email: 'user1@example.com', name: '홍길동', phonenumber: 1023456789, role: 'user', created_at: '2025-01-10', update_at: '2025-01-10' },
        { id: 3, email: 'user2@example.com', name: '김철수', phonenumber: 1034567890, role: 'user', created_at: '2025-01-12', update_at: '2025-01-12' },
      ]);
    } finally {
      setIsLoading(false);
    }
  }, []);

  useEffect(() => {
    loadUsers();
  }, [loadUsers]);

  // 검색
  const handleSearch = async () => {
    if (!searchTerm.trim()) {
      loadUsers();
      return;
    }
    try {
      setIsLoading(true);
      const data = await searchUsers({ search: searchTerm });
      setUsers(data);
    } catch (error) {
      console.error('검색 실패:', error);
    } finally {
      setIsLoading(false);
    }
  };

  // 검색어 입력 시 Enter 키
  const handleSearchKeyPress = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter') {
      handleSearch();
    }
  };

  // 상세 보기 모달 열기
  const handleViewDetail = async (userId: number) => {
    try {
      const data = await getUserDetail({ userid: userId });
      setDetailUser(data);
    } catch (error) {
      console.error('상세 조회 실패:', error);
      // 더미 데이터로 대체
      const user = users.find((u) => u.id === userId);
      if (user) setDetailUser(user);
    }
  };

  // 채팅 기록 모달 열기
  const handleViewHistory = async (user: AdminUser) => {
    setHistoryUser(user);
    setIsHistoryLoading(true);
    try {
      const data = await getUserHistory({ userid: user.id });
      setChatHistory(data);
    } catch (error) {
      console.error('채팅 기록 조회 실패:', error);
      // 더미 데이터
      setChatHistory([
        { chatRoomId: 1, roomName: '도면 분석 문의', createdAt: '2025-01-20', user },
        { chatRoomId: 2, roomName: '일반 상담', createdAt: '2025-01-18', user },
      ]);
    } finally {
      setIsHistoryLoading(false);
    }
  };

  // 수정 모달 열기
  const openEditModal = (user: AdminUser) => {
    setEditingUser(user);
    setEditForm({
      name: user.name,
      phone: user.phonenumber?.toString() || '',
      role: user.role,
    });
  };

  // 수정 저장
  const handleSaveEdit = async () => {
    if (!editingUser) return;
    try {
      await editUser({
        userid: editingUser.id,
        name: editForm.name || undefined,
        phone: editForm.phone ? parseInt(editForm.phone) : undefined,
        role: editForm.role || undefined,
      });
      alert('수정되었습니다.');
      setEditingUser(null);
      loadUsers();
    } catch (error) {
      console.error('수정 실패:', error);
      alert('수정에 실패했습니다.');
    }
  };

  // 단일 삭제
  const handleDelete = async (userId: number) => {
    if (!window.confirm('정말 삭제하시겠습니까?')) return;
    try {
      await deleteEntities('user', [userId]);
      alert('삭제되었습니다.');
      loadUsers();
    } catch (error) {
      console.error('삭제 실패:', error);
      alert('삭제에 실패했습니다.');
    }
  };

  // 선택 삭제
  const handleDeleteSelected = async () => {
    if (selectedIds.length === 0) {
      alert('삭제할 유저를 선택하세요.');
      return;
    }
    if (!window.confirm(`${selectedIds.length}명의 유저를 삭제하시겠습니까?`)) return;
    try {
      await deleteEntities('user', selectedIds);
      alert('삭제되었습니다.');
      setSelectedIds([]);
      loadUsers();
    } catch (error) {
      console.error('삭제 실패:', error);
      alert('삭제에 실패했습니다.');
    }
  };

  // 체크박스 토글
  const toggleSelect = (id: number) => {
    setSelectedIds((prev) =>
      prev.includes(id) ? prev.filter((i) => i !== id) : [...prev, id]
    );
  };

  // 전체 선택
  const toggleSelectAll = () => {
    if (selectedIds.length === users.length) {
      setSelectedIds([]);
    } else {
      setSelectedIds(users.map((u) => u.id));
    }
  };

  return (
    <AdminLayout>
      <div className={styles.page}>
        <div className={styles.pageHeader}>
          <h2 className={styles.pageTitle}>사용자 관리</h2>
          {selectedIds.length > 0 && (
            <button className={styles.dangerBtn} onClick={handleDeleteSelected}>
              선택 삭제 ({selectedIds.length})
            </button>
          )}
        </div>

        {/* 검색 */}
        <div className={styles.toolbar}>
          <input
            type="text"
            placeholder="이메일 또는 이름으로 검색..."
            value={searchTerm}
            onChange={(e) => setSearchTerm(e.target.value)}
            onKeyPress={handleSearchKeyPress}
            className={styles.searchInput}
          />
          <button className={styles.searchBtn} onClick={handleSearch}>검색</button>
        </div>

        {/* 테이블 */}
        <div className={styles.tableCard}>
          {isLoading ? (
            <p className={styles.loadingText}>로딩 중...</p>
          ) : (
            <table className={styles.table}>
              <thead>
                <tr>
                  <th>
                    <input
                      type="checkbox"
                      checked={selectedIds.length === users.length && users.length > 0}
                      onChange={toggleSelectAll}
                    />
                  </th>
                  <th>이메일</th>
                  <th>이름</th>
                  <th>전화번호</th>
                  <th>역할</th>
                  <th>가입일</th>
                  <th>관리</th>
                </tr>
              </thead>
              <tbody>
                {users.map((user) => (
                  <tr key={user.id}>
                    <td>
                      <input
                        type="checkbox"
                        checked={selectedIds.includes(user.id)}
                        onChange={() => toggleSelect(user.id)}
                      />
                    </td>
                    <td>{user.email}</td>
                    <td>{user.name}</td>
                    <td>{user.phonenumber || '-'}</td>
                    <td>
                      <span className={`${styles.badge} ${styles[user.role]}`}>
                        {user.role === 'admin' ? '관리자' : '사용자'}
                      </span>
                    </td>
                    <td>{user.created_at?.split('T')[0]}</td>
                    <td>
                      <div className={styles.actions}>
                        <button className={styles.actionBtn} title="상세 보기" onClick={() => handleViewDetail(user.id)}>
                          <FiEye />
                        </button>
                        <button className={styles.actionBtn} title="채팅 기록" onClick={() => handleViewHistory(user)}>
                          <FiMessageSquare />
                        </button>
                        <button className={styles.actionBtn} title="수정" onClick={() => openEditModal(user)}>
                          <FiEdit2 />
                        </button>
                        <button className={styles.actionBtn} title="삭제" onClick={() => handleDelete(user.id)}>
                          <FiTrash2 />
                        </button>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>

        <div className={styles.pagination}>
          <span className={styles.pageInfo}>총 {users.length}명</span>
        </div>
      </div>

      {/* 상세 보기 모달 */}
      {detailUser && (
        <div className={styles.modalOverlay} onClick={() => setDetailUser(null)}>
          <div className={styles.modal} onClick={(e) => e.stopPropagation()}>
            <div className={styles.modalHeader}>
              <h3>유저 상세 정보</h3>
              <button className={styles.closeBtn} onClick={() => setDetailUser(null)}>
                <FiX />
              </button>
            </div>
            <div className={styles.modalBody}>
              <div className={styles.formGroup}>
                <label>ID</label>
                <input type="text" value={detailUser.id} disabled />
              </div>
              <div className={styles.formGroup}>
                <label>이메일</label>
                <input type="text" value={detailUser.email} disabled />
              </div>
              <div className={styles.formGroup}>
                <label>이름</label>
                <input type="text" value={detailUser.name} disabled />
              </div>
              <div className={styles.formGroup}>
                <label>전화번호</label>
                <input type="text" value={detailUser.phonenumber || '-'} disabled />
              </div>
              <div className={styles.formGroup}>
                <label>역할</label>
                <input type="text" value={detailUser.role === 'admin' ? '관리자' : '사용자'} disabled />
              </div>
              <div className={styles.formGroup}>
                <label>가입일</label>
                <input type="text" value={detailUser.created_at?.split('T')[0]} disabled />
              </div>
              <div className={styles.formGroup}>
                <label>최근 수정일</label>
                <input type="text" value={detailUser.update_at?.split('T')[0]} disabled />
              </div>
            </div>
            <div className={styles.modalFooter}>
              <button className={styles.cancelBtn} onClick={() => setDetailUser(null)}>닫기</button>
            </div>
          </div>
        </div>
      )}

      {/* 채팅 기록 모달 */}
      {historyUser && (
        <div className={styles.modalOverlay} onClick={() => setHistoryUser(null)}>
          <div className={styles.modal} onClick={(e) => e.stopPropagation()}>
            <div className={styles.modalHeader}>
              <h3>{historyUser.name}님의 채팅 기록</h3>
              <button className={styles.closeBtn} onClick={() => setHistoryUser(null)}>
                <FiX />
              </button>
            </div>
            <div className={styles.modalBody}>
              {isHistoryLoading ? (
                <p className={styles.loadingText}>로딩 중...</p>
              ) : chatHistory.length === 0 ? (
                <p className={styles.emptyText}>채팅 기록이 없습니다.</p>
              ) : (
                <div className={styles.historyList}>
                  {chatHistory.map((chat) => (
                    <div key={chat.chatRoomId} className={styles.historyItem}>
                      <div className={styles.historyInfo}>
                        <span className={styles.historyName}>{chat.roomName}</span>
                        <span className={styles.historyDate}>{chat.createdAt?.split('T')[0]}</span>
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </div>
            <div className={styles.modalFooter}>
              <button className={styles.cancelBtn} onClick={() => setHistoryUser(null)}>닫기</button>
            </div>
          </div>
        </div>
      )}

      {/* 수정 모달 */}
      {editingUser && (
        <div className={styles.modalOverlay} onClick={() => setEditingUser(null)}>
          <div className={styles.modal} onClick={(e) => e.stopPropagation()}>
            <div className={styles.modalHeader}>
              <h3>유저 정보 수정</h3>
              <button className={styles.closeBtn} onClick={() => setEditingUser(null)}>
                <FiX />
              </button>
            </div>
            <div className={styles.modalBody}>
              <div className={styles.formGroup}>
                <label>이메일 (변경 불가)</label>
                <input type="text" value={editingUser.email} disabled />
              </div>
              <div className={styles.formGroup}>
                <label>이름</label>
                <input
                  type="text"
                  value={editForm.name}
                  onChange={(e) => setEditForm({ ...editForm, name: e.target.value })}
                />
              </div>
              <div className={styles.formGroup}>
                <label>전화번호</label>
                <input
                  type="text"
                  value={editForm.phone}
                  onChange={(e) => setEditForm({ ...editForm, phone: e.target.value })}
                />
              </div>
              <div className={styles.formGroup}>
                <label>역할</label>
                <select
                  value={editForm.role}
                  onChange={(e) => setEditForm({ ...editForm, role: e.target.value })}
                >
                  <option value="user">사용자</option>
                  <option value="admin">관리자</option>
                </select>
              </div>
            </div>
            <div className={styles.modalFooter}>
              <button className={styles.cancelBtn} onClick={() => setEditingUser(null)}>취소</button>
              <button className={styles.primaryBtn} onClick={handleSaveEdit}>저장</button>
            </div>
          </div>
        </div>
      )}
    </AdminLayout>
  );
}
