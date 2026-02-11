// ============================================
// FloorPlansPage - Floor Plan Database Management
// ============================================

import { useState, useEffect, useCallback, useRef, useMemo } from 'react';
import { FiSearch, FiTrash2, FiX, FiFilter, FiChevronDown, FiChevronUp, FiZoomIn, FiZoomOut, FiMaximize2 } from 'react-icons/fi';
import { AdminLayout } from '../components/AdminLayout';
import { getFloorPlans, searchFloorPlans, getFloorPlanDetail, deleteEntities } from '../api/admin.api';
import type { AdminFloorPlan, SearchFloorPlanRequest } from '../types/admin.types';
import { BASE_URL } from '@/shared/api/axios';
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
  });

  // 페이지네이션 상태
  const [currentPage, setCurrentPage] = useState(1);
  const itemsPerPage = 8;

  // 상세 모달 상태
  const [detailPlan, setDetailPlan] = useState<AdminFloorPlan | null>(null);

  // 이미지 확대/축소 상태
  const [imageScale, setImageScale] = useState(1);
  const [imagePosition, setImagePosition] = useState({ x: 0, y: 0 });
  const [isDragging, setIsDragging] = useState(false);
  const [dragStart, setDragStart] = useState({ x: 0, y: 0 });
  const imageContainerRef = useRef<HTMLDivElement>(null);

  // 마우스 휠 이벤트 리스너 등록 (passive: false)
  useEffect(() => {
    const container = imageContainerRef.current;
    if (!container) return;

    const handleWheel = (e: WheelEvent) => {
      e.preventDefault();
      if (e.deltaY < 0) {
        setImageScale(prev => Math.min(prev + 0.25, 5));
      } else {
        setImageScale(prev => Math.max(prev - 0.25, 0.5));
      }
    };

    container.addEventListener('wheel', handleWheel, { passive: false });
    return () => {
      container.removeEventListener('wheel', handleWheel);
    };
  }, [detailPlan]);

  // 도면 목록 로드
  const loadFloorPlans = useCallback(async () => {
    try {
      setIsLoading(true);
      const data = await getFloorPlans();
      setFloorPlans(data);
    } catch (error) {
      console.error('도면 목록 로드 실패:', error);
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
      setCurrentPage(1);
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

    // 모든 필터가 비어있으면 전체 목록 로드
    if (Object.keys(params).length === 0) {
      loadFloorPlans();
      return;
    }

    try {
      setIsLoading(true);
      const data = await searchFloorPlans(params);
      setFloorPlans(data);
      setCurrentPage(1);
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
    });
    setSearchTerm('');
    setCurrentPage(1);
    loadFloorPlans();
  };

  // 현재 페이지의 도면
  const currentFloorPlans = useMemo(() => {
    const startIndex = (currentPage - 1) * itemsPerPage;
    const endIndex = startIndex + itemsPerPage;
    return floorPlans.slice(startIndex, endIndex);
  }, [floorPlans, currentPage, itemsPerPage]);

  // 전체 페이지 수
  const totalPages = Math.ceil(floorPlans.length / itemsPerPage);

  // 상세 보기
  const handleViewDetail = async (floorplanId: number) => {
    try {
      const data = await getFloorPlanDetail({ floorplanid: floorplanId });
      setDetailPlan(data);
      // 이미지 확대/축소 상태 초기화
      setImageScale(1);
      setImagePosition({ x: 0, y: 0 });
    } catch (error) {
      console.error('상세 조회 실패:', error);
    }
  };

  // 이미지 확대
  const handleZoomIn = () => {
    setImageScale(prev => Math.min(prev + 0.25, 5));
  };

  // 이미지 축소
  const handleZoomOut = () => {
    setImageScale(prev => Math.max(prev - 0.25, 0.5));
  };

  // 이미지 원본 크기
  const handleZoomReset = () => {
    setImageScale(1);
    setImagePosition({ x: 0, y: 0 });
  };

  // 드래그 시작
  const handleMouseDown = (e: React.MouseEvent) => {
    if (imageScale > 1) {
      setIsDragging(true);
      setDragStart({ x: e.clientX - imagePosition.x, y: e.clientY - imagePosition.y });
    }
  };

  // 드래그 중
  const handleMouseMove = (e: React.MouseEvent) => {
    if (isDragging && imageScale > 1) {
      setImagePosition({
        x: e.clientX - dragStart.x,
        y: e.clientY - dragStart.y
      });
    }
  };

  // 드래그 종료
  const handleMouseUp = () => {
    setIsDragging(false);
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
    if (selectedIds.length === currentFloorPlans.length && currentFloorPlans.length > 0) {
      setSelectedIds([]);
    } else {
      setSelectedIds(currentFloorPlans.map((p) => p.id));
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
                      checked={selectedIds.length === currentFloorPlans.length && currentFloorPlans.length > 0}
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
                {currentFloorPlans.map((plan) => (
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
          <span className={styles.pageInfo}>총 {floorPlans.length}개 도면 (페이지 {currentPage}/{totalPages})</span>
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

      {/* 도면 이미지 모달 */}
      {detailPlan && (
        <div className={styles.modalOverlay} onClick={() => setDetailPlan(null)}>
          <div className={styles.imageModal} onClick={(e) => e.stopPropagation()}>
            <div className={styles.modalHeader}>
              <h3>{detailPlan.name}</h3>
              <div className={styles.imageControls}>
                <button className={styles.zoomBtn} onClick={handleZoomOut} title="축소">
                  <FiZoomOut />
                </button>
                <span className={styles.zoomLevel}>{Math.round(imageScale * 100)}%</span>
                <button className={styles.zoomBtn} onClick={handleZoomIn} title="확대">
                  <FiZoomIn />
                </button>
                <button className={styles.zoomBtn} onClick={handleZoomReset} title="원본 크기">
                  <FiMaximize2 />
                </button>
              </div>
              <button className={styles.closeBtn} onClick={() => setDetailPlan(null)}>
                <FiX />
              </button>
            </div>
            <div 
              ref={imageContainerRef}
              className={styles.imageModalBody}
              onMouseDown={handleMouseDown}
              onMouseMove={handleMouseMove}
              onMouseUp={handleMouseUp}
              onMouseLeave={handleMouseUp}
              style={{ cursor: imageScale > 1 ? (isDragging ? 'grabbing' : 'grab') : 'default' }}
            >
              {detailPlan.imageUrl ? (
                <img 
                  src={`${BASE_URL}/api/admin/floorplan/${detailPlan.id}/image`} 
                  alt={detailPlan.name}
                  style={{ 
                    transform: `scale(${imageScale}) translate(${imagePosition.x / imageScale}px, ${imagePosition.y / imageScale}px)`,
                    transition: isDragging ? 'none' : 'transform 0.2s ease',
                    maxWidth: '100%',
                    maxHeight: '100%',
                    objectFit: 'contain',
                    display: 'block',
                    userSelect: 'none',
                    pointerEvents: 'none'
                  }}
                  onError={(e) => {
                    console.error('이미지 로드 실패:', detailPlan.imageUrl);
                    (e.target as HTMLImageElement).style.display = 'none';
                    const container = (e.target as HTMLImageElement).parentElement;
                    if (container) {
                      container.innerHTML = `
                        <div style="text-align: center; padding: 40px; color: #999;">
                          <p>이미지를 불러올 수 없습니다.</p>
                          <p style="font-size: 12px; margin-top: 10px;">${detailPlan.imageUrl}</p>
                        </div>
                      `;
                    }
                  }}
                  onLoad={() => {
                    console.log('이미지 로드 성공:', detailPlan.imageUrl);
                  }}
                />
              ) : (
                <div style={{ textAlign: 'center', padding: '40px', color: '#999' }}>
                  <p>이미지 URL이 없습니다.</p>
                </div>
              )}
            </div>
          </div>
        </div>
      )}
    </AdminLayout>
  );
}
