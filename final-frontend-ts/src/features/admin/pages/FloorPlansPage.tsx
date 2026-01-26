// ============================================
// FloorPlansPage - Floor Plan Database Management
// ============================================

import { useState, useEffect, useCallback } from 'react';
import { FiSearch, FiTrash2, FiX, FiFilter, FiChevronDown, FiChevronUp } from 'react-icons/fi';
import { AdminLayout } from '../components/AdminLayout';
import { getFloorPlans, searchFloorPlans, getFloorPlanDetail, deleteEntities } from '../api';
import type { AdminFloorPlan, SearchFloorPlanRequest } from '../types';
import styles from './AdminPages.module.css';

export function FloorPlansPage() {
  const [floorPlans, setFloorPlans] = useState<AdminFloorPlan[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [selectedIds, setSelectedIds] = useState<number[]>([]);

  // 기본 검색
  const [searchTerm, setSearchTerm] = useState('');

  // 고급 검색 필터
  const [showAdvancedSearch, setShowAdvancedSearch] = useState(false);
  const [advancedFilters, setAdvancedFilters] = useState<SearchFloorPlanRequest>({
    name: '',
    uploaderEmail: '',
    startDate: '',
    endDate: '',
    minRooms: undefined,
    maxRooms: undefined,
    roomName: '',
    objName: '',
    strName: '',
  });

  // 상세 모달 상태
  const [detailPlan, setDetailPlan] = useState<AdminFloorPlan | null>(null);

  // 도면 목록 로드
  const loadFloorPlans = useCallback(async () => {
    try {
      setIsLoading(true);
      const data = await getFloorPlans();
      setFloorPlans(data);
    } catch (error) {
      console.error('도면 목록 로드 실패:', error);
      // 백엔드 연결 안 되면 더미 데이터
      setFloorPlans([
        { id: 1, name: '강남역 오피스빌딩 1층', imageUrl: '/images/plan1.png', user: { id: 1, email: 'user1@example.com', name: '홍길동', phonenumber: 0, role: 'user', create_at: '', update_at: '' }, createdAt: '2025-01-20' },
        { id: 2, name: '판교 테크노밸리 3층', imageUrl: '/images/plan2.png', user: { id: 2, email: 'user2@example.com', name: '김철수', phonenumber: 0, role: 'user', create_at: '', update_at: '' }, createdAt: '2025-01-19' },
        { id: 3, name: '홍대입구 상가 B1층', imageUrl: '/images/plan3.png', user: { id: 1, email: 'user1@example.com', name: '홍길동', phonenumber: 0, role: 'user', create_at: '', update_at: '' }, createdAt: '2025-01-18' },
      ]);
    } finally {
      setIsLoading(false);
    }
  }, []);

  useEffect(() => {
    loadFloorPlans();
  }, [loadFloorPlans]);

  // 기본 검색
  const handleSearch = async () => {
    if (!searchTerm.trim()) {
      loadFloorPlans();
      return;
    }
    try {
      setIsLoading(true);
      const data = await searchFloorPlans({ name: searchTerm });
      setFloorPlans(data);
    } catch (error) {
      console.error('검색 실패:', error);
    } finally {
      setIsLoading(false);
    }
  };

  const handleSearchKeyPress = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter') {
      handleSearch();
    }
  };

  // 고급 검색
  const handleAdvancedSearch = async () => {
    // 빈 값 필터링
    const params: SearchFloorPlanRequest = {};
    if (advancedFilters.name?.trim()) params.name = advancedFilters.name;
    if (advancedFilters.uploaderEmail?.trim()) params.uploaderEmail = advancedFilters.uploaderEmail;
    if (advancedFilters.startDate) params.startDate = advancedFilters.startDate;
    if (advancedFilters.endDate) params.endDate = advancedFilters.endDate;
    if (advancedFilters.minRooms !== undefined && advancedFilters.minRooms > 0) params.minRooms = advancedFilters.minRooms;
    if (advancedFilters.maxRooms !== undefined && advancedFilters.maxRooms > 0) params.maxRooms = advancedFilters.maxRooms;
    if (advancedFilters.roomName?.trim()) params.roomName = advancedFilters.roomName;
    if (advancedFilters.objName?.trim()) params.objName = advancedFilters.objName;
    if (advancedFilters.strName?.trim()) params.strName = advancedFilters.strName;

    // 모든 필터가 비어있으면 전체 목록 로드
    if (Object.keys(params).length === 0) {
      loadFloorPlans();
      return;
    }

    try {
      setIsLoading(true);
      const data = await searchFloorPlans(params);
      setFloorPlans(data);
    } catch (error) {
      console.error('고급 검색 실패:', error);
    } finally {
      setIsLoading(false);
    }
  };

  // 필터 초기화
  const resetFilters = () => {
    setAdvancedFilters({
      name: '',
      uploaderEmail: '',
      startDate: '',
      endDate: '',
      minRooms: undefined,
      maxRooms: undefined,
      roomName: '',
      objName: '',
      strName: '',
    });
    setSearchTerm('');
    loadFloorPlans();
  };

  // 상세 보기
  const handleViewDetail = async (floorplanId: number) => {
    try {
      const data = await getFloorPlanDetail({ floorplanid: floorplanId });
      setDetailPlan(data);
    } catch (error) {
      console.error('상세 조회 실패:', error);
      // 더미 데이터로 대체
      const plan = floorPlans.find((p) => p.id === floorplanId);
      if (plan) setDetailPlan(plan);
    }
  };

  // 단일 삭제
  const handleDelete = async (planId: number) => {
    if (!window.confirm('정말 삭제하시겠습니까?')) return;
    try {
      await deleteEntities('floorplan', [planId]);
      alert('삭제되었습니다.');
      loadFloorPlans();
    } catch (error) {
      console.error('삭제 실패:', error);
      alert('삭제에 실패했습니다.');
    }
  };

  // 선택 삭제
  const handleDeleteSelected = async () => {
    if (selectedIds.length === 0) {
      alert('삭제할 도면을 선택하세요.');
      return;
    }
    if (!window.confirm(`${selectedIds.length}개의 도면을 삭제하시겠습니까?`)) return;
    try {
      await deleteEntities('floorplan', selectedIds);
      alert('삭제되었습니다.');
      setSelectedIds([]);
      loadFloorPlans();
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
    if (selectedIds.length === floorPlans.length) {
      setSelectedIds([]);
    } else {
      setSelectedIds(floorPlans.map((p) => p.id));
    }
  };

  return (
    <AdminLayout>
      <div className={styles.page}>
        <div className={styles.pageHeader}>
          <h2 className={styles.pageTitle}>도면 DB 관리</h2>
          {selectedIds.length > 0 && (
            <button className={styles.dangerBtn} onClick={handleDeleteSelected}>
              선택 삭제 ({selectedIds.length})
            </button>
          )}
        </div>

        {/* 기본 검색 */}
        <div className={styles.toolbar}>
          <input
            type="text"
            placeholder="도면명으로 검색..."
            value={searchTerm}
            onChange={(e) => setSearchTerm(e.target.value)}
            onKeyPress={handleSearchKeyPress}
            className={styles.searchInput}
          />
          <button className={styles.searchBtn} onClick={handleSearch}>검색</button>
          <button
            className={styles.filterToggleBtn}
            onClick={() => setShowAdvancedSearch(!showAdvancedSearch)}
          >
            <FiFilter />
            고급 검색
            {showAdvancedSearch ? <FiChevronUp /> : <FiChevronDown />}
          </button>
        </div>

        {/* 고급 검색 패널 */}
        {showAdvancedSearch && (
          <div className={styles.advancedSearchPanel}>
            <div className={styles.filterGrid}>
              <div className={styles.filterGroup}>
                <label>도면명</label>
                <input
                  type="text"
                  placeholder="도면명"
                  value={advancedFilters.name || ''}
                  onChange={(e) => setAdvancedFilters({ ...advancedFilters, name: e.target.value })}
                />
              </div>
              <div className={styles.filterGroup}>
                <label>업로더 이메일</label>
                <input
                  type="text"
                  placeholder="이메일"
                  value={advancedFilters.uploaderEmail || ''}
                  onChange={(e) => setAdvancedFilters({ ...advancedFilters, uploaderEmail: e.target.value })}
                />
              </div>
              <div className={styles.filterGroup}>
                <label>시작일</label>
                <input
                  type="date"
                  value={advancedFilters.startDate || ''}
                  onChange={(e) => setAdvancedFilters({ ...advancedFilters, startDate: e.target.value })}
                />
              </div>
              <div className={styles.filterGroup}>
                <label>종료일</label>
                <input
                  type="date"
                  value={advancedFilters.endDate || ''}
                  onChange={(e) => setAdvancedFilters({ ...advancedFilters, endDate: e.target.value })}
                />
              </div>
              <div className={styles.filterGroup}>
                <label>최소 공간 수</label>
                <input
                  type="number"
                  placeholder="최소"
                  min={0}
                  value={advancedFilters.minRooms || ''}
                  onChange={(e) => setAdvancedFilters({ ...advancedFilters, minRooms: e.target.value ? parseInt(e.target.value) : undefined })}
                />
              </div>
              <div className={styles.filterGroup}>
                <label>최대 공간 수</label>
                <input
                  type="number"
                  placeholder="최대"
                  min={0}
                  value={advancedFilters.maxRooms || ''}
                  onChange={(e) => setAdvancedFilters({ ...advancedFilters, maxRooms: e.target.value ? parseInt(e.target.value) : undefined })}
                />
              </div>
              <div className={styles.filterGroup}>
                <label>공간명</label>
                <input
                  type="text"
                  placeholder="거실, 침실 등"
                  value={advancedFilters.roomName || ''}
                  onChange={(e) => setAdvancedFilters({ ...advancedFilters, roomName: e.target.value })}
                />
              </div>
              <div className={styles.filterGroup}>
                <label>객체명</label>
                <input
                  type="text"
                  placeholder="소파, 침대 등"
                  value={advancedFilters.objName || ''}
                  onChange={(e) => setAdvancedFilters({ ...advancedFilters, objName: e.target.value })}
                />
              </div>
              <div className={styles.filterGroup}>
                <label>구조물명</label>
                <input
                  type="text"
                  placeholder="문, 창문 등"
                  value={advancedFilters.strName || ''}
                  onChange={(e) => setAdvancedFilters({ ...advancedFilters, strName: e.target.value })}
                />
              </div>
            </div>
            <div className={styles.filterActions}>
              <button className={styles.resetBtn} onClick={resetFilters}>초기화</button>
              <button className={styles.primaryBtn} onClick={handleAdvancedSearch}>검색</button>
            </div>
          </div>
        )}

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
                      checked={selectedIds.length === floorPlans.length && floorPlans.length > 0}
                      onChange={toggleSelectAll}
                    />
                  </th>
                  <th>도면명</th>
                  <th>업로더</th>
                  <th>업로드일</th>
                  <th>관리</th>
                </tr>
              </thead>
              <tbody>
                {floorPlans.map((plan) => (
                  <tr key={plan.id}>
                    <td>
                      <input
                        type="checkbox"
                        checked={selectedIds.includes(plan.id)}
                        onChange={() => toggleSelect(plan.id)}
                      />
                    </td>
                    <td>
                      <div className={styles.planName}>
                        <span className={styles.planIcon}>📋</span>
                        {plan.name}
                      </div>
                    </td>
                    <td>{plan.user?.email || '-'}</td>
                    <td>{plan.createdAt?.split('T')[0]}</td>
                    <td>
                      <div className={styles.actions}>
                        <button className={styles.actionBtn} title="보기" onClick={() => handleViewDetail(plan.id)}>
                          <FiSearch />
                        </button>
                        <button className={styles.actionBtn} title="삭제" onClick={() => handleDelete(plan.id)}>
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
          <span className={styles.pageInfo}>총 {floorPlans.length}개 도면</span>
        </div>
      </div>

      {/* 상세 모달 */}
      {detailPlan && (
        <div className={styles.modalOverlay} onClick={() => setDetailPlan(null)}>
          <div className={styles.modal} onClick={(e) => e.stopPropagation()}>
            <div className={styles.modalHeader}>
              <h3>도면 상세 정보</h3>
              <button className={styles.closeBtn} onClick={() => setDetailPlan(null)}>
                <FiX />
              </button>
            </div>
            <div className={styles.modalBody}>
              <div className={styles.formGroup}>
                <label>도면명</label>
                <input type="text" value={detailPlan.name} disabled />
              </div>
              <div className={styles.formGroup}>
                <label>업로더</label>
                <input type="text" value={detailPlan.user?.email || '-'} disabled />
              </div>
              <div className={styles.formGroup}>
                <label>업로드일</label>
                <input type="text" value={detailPlan.createdAt?.split('T')[0]} disabled />
              </div>
              <div className={styles.formGroup}>
                <label>이미지 URL</label>
                <input type="text" value={detailPlan.imageUrl || '-'} disabled />
              </div>
              {detailPlan.rooms && detailPlan.rooms.length > 0 && (
                <div className={styles.formGroup}>
                  <label>공간 목록 ({detailPlan.rooms.length}개)</label>
                  <div className={styles.detailList}>
                    {detailPlan.rooms.map((room) => (
                      <div key={room.id} className={styles.detailListItem}>
                        {room.spcname} ({room.ocrname})
                      </div>
                    ))}
                  </div>
                </div>
              )}
              {detailPlan.objs && detailPlan.objs.length > 0 && (
                <div className={styles.formGroup}>
                  <label>객체 목록 ({detailPlan.objs.length}개)</label>
                  <div className={styles.detailList}>
                    {detailPlan.objs.map((obj) => (
                      <div key={obj.id} className={styles.detailListItem}>
                        {obj.name}
                      </div>
                    ))}
                  </div>
                </div>
              )}
              {detailPlan.strs && detailPlan.strs.length > 0 && (
                <div className={styles.formGroup}>
                  <label>구조물 목록 ({detailPlan.strs.length}개)</label>
                  <div className={styles.detailList}>
                    {detailPlan.strs.map((str) => (
                      <div key={str.id} className={styles.detailListItem}>
                        {str.name}
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </div>
            <div className={styles.modalFooter}>
              <button className={styles.cancelBtn} onClick={() => setDetailPlan(null)}>닫기</button>
            </div>
          </div>
        </div>
      )}
    </AdminLayout>
  );
}
