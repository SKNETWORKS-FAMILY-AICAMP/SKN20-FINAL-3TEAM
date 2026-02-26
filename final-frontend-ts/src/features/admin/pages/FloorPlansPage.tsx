// ============================================
// FloorPlansPage - Floor Plan Database Management
// ============================================

import { useState, useEffect, useCallback, useRef } from 'react';
import { useSearchParams } from 'react-router-dom';
import { FiX, FiFilter, FiChevronDown, FiChevronUp, FiZoomIn, FiZoomOut, FiMaximize2, FiSearch } from 'react-icons/fi';
import { AdminLayout } from '../components/AdminLayout';
import { getFloorPlans, searchFloorPlans, getFloorPlanDetail, deleteEntities } from '../api/admin.api';
import type { AdminFloorPlan, SearchFloorPlanRequest } from '../types/admin.types';
import styles from './AdminPages.module.css';

export function FloorPlansPage() {
  const [searchParams, setSearchParams] = useSearchParams();
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

  // 서버 사이드 페이징 상태 (0-based)
  const [currentPage, setCurrentPage] = useState(0);
  const [totalPages, setTotalPages] = useState(0);
  const [totalElements, setTotalElements] = useState(0);
  const itemsPerPage = 8;

  // 검색 활성 여부 추적
  const [isSearchActive, setIsSearchActive] = useState(false);

  // 상세 모달 상태
  const [detailPlan, setDetailPlan] = useState<AdminFloorPlan | null>(null);

  // 삭제 확인 모달 상태
  const [confirmModal, setConfirmModal] = useState<{ ids: number[]; message: string } | null>(null);

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

  // 도면 목록 로드 (서버 사이드 페이징)
  const loadFloorPlans = useCallback(async (page: number = 0) => {
    try {
      setIsLoading(true);
      const data = await getFloorPlans(page, itemsPerPage);
      setFloorPlans(data.content);
      setCurrentPage(data.currentPage);
      setTotalPages(data.totalPages);
      setTotalElements(data.totalElements);
      setIsSearchActive(false);
    } catch (error) {
      console.error('도면 목록 로드 실패:', error);
    } finally {
      setIsLoading(false);
    }
  }, []);

  useEffect(() => {
    const initSearch = searchParams.get('search');
    if (initSearch) {
      setSearchTerm(initSearch);
      // 서버 사이드 검색
      (async () => {
        try {
          setIsLoading(true);
          const data = await searchFloorPlans({ name: initSearch, page: 0, size: itemsPerPage });
          setFloorPlans(data.content);
          setCurrentPage(data.currentPage);
          setTotalPages(data.totalPages);
          setTotalElements(data.totalElements);
          setIsSearchActive(true);
        } catch (error) {
          console.error('검색 실패:', error);
        } finally {
          setIsLoading(false);
        }
      })();
      // 쿼리 파라미터 제거 (뒤로가기 시 재검색 방지)
      setSearchParams({}, { replace: true });
    } else {
      loadFloorPlans();
    }
  }, []);

  // 기본 검색
  const handleSearch = async () => {
    if (!searchTerm.trim()) {
      loadFloorPlans();
      return;
    }
    try {
      setIsLoading(true);
      const data = await searchFloorPlans({ name: searchTerm.trim(), page: 0, size: itemsPerPage });
      setFloorPlans(data.content);
      setCurrentPage(data.currentPage);
      setTotalPages(data.totalPages);
      setTotalElements(data.totalElements);
      setIsSearchActive(true);
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

  // 고급 검색 (서버 사이드 페이징)
  const handleAdvancedSearch = async (page: number = 0) => {
    // 빈 값 필터링
    const params: SearchFloorPlanRequest = { page, size: itemsPerPage };
    if (advancedFilters.name?.trim()) params.name = advancedFilters.name;
    if (advancedFilters.uploaderEmail?.trim()) params.uploaderEmail = advancedFilters.uploaderEmail;
    if (advancedFilters.startDate) params.startDate = advancedFilters.startDate;
    if (advancedFilters.endDate) params.endDate = advancedFilters.endDate;
    if (advancedFilters.minRooms !== undefined && advancedFilters.minRooms > 0) params.minRooms = advancedFilters.minRooms;
    if (advancedFilters.maxRooms !== undefined && advancedFilters.maxRooms > 0) params.maxRooms = advancedFilters.maxRooms;

    // page/size 외 모든 필터가 비어있으면 전체 목록 로드
    const hasFilter = params.name || params.uploaderEmail || params.startDate || params.endDate || params.minRooms || params.maxRooms;
    if (!hasFilter) {
      loadFloorPlans();
      return;
    }

    try {
      setIsLoading(true);
      const data = await searchFloorPlans(params);
      setFloorPlans(data.content);
      setCurrentPage(data.currentPage);
      setTotalPages(data.totalPages);
      setTotalElements(data.totalElements);
      setIsSearchActive(true);
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
    setIsSearchActive(false);
    loadFloorPlans(0);
  };

  // 페이지 변경 핸들러
  const handlePageChange = (newPage: number) => {
    setSelectedIds([]);
    if (isSearchActive) {
      // 검색 중이면 검색 조건 유지하며 페이지만 변경
      if (searchTerm.trim() && !showAdvancedSearch) {
        // 기본 검색
        (async () => {
          try {
            setIsLoading(true);
            const data = await searchFloorPlans({ name: searchTerm.trim(), page: newPage, size: itemsPerPage });
            setFloorPlans(data.content);
            setCurrentPage(data.currentPage);
            setTotalPages(data.totalPages);
            setTotalElements(data.totalElements);
          } catch (error) {
            console.error('검색 실패:', error);
          } finally {
            setIsLoading(false);
          }
        })();
      } else {
        // 고급 검색
        handleAdvancedSearch(newPage);
      }
    } else {
      loadFloorPlans(newPage);
    }
  };

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

  // 단일 삭제 - 확인 모달 열기
  const handleDelete = (planId: number) => {
    setConfirmModal({ ids: [planId], message: '이 도면을 삭제하면 S3에 저장된 이미지도 함께 삭제되며, 이전 채팅에서 해당 이미지를 불러올 수 없게 됩니다.' });
  };

  // 선택 삭제 - 확인 모달 열기
  const handleDeleteSelected = () => {
    if (selectedIds.length === 0) {
      alert('삭제할 도면을 선택하세요.');
      return;
    }
    setConfirmModal({ ids: selectedIds, message: `${selectedIds.length}개의 도면을 삭제하면 S3에 저장된 이미지도 함께 삭제되며, 이전 채팅에서 해당 이미지를 불러올 수 없게 됩니다.` });
  };

  // 삭제 실행
  const executeDelete = async () => {
    if (!confirmModal) return;
    try {
      await deleteEntities('floorplan', confirmModal.ids);
      setConfirmModal(null);
      setSelectedIds([]);
      // 현재 페이지 새로고침
      if (isSearchActive) {
        handlePageChange(currentPage);
      } else {
        loadFloorPlans(currentPage);
      }
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

  // 전체 선택 (현재 페이지)
  const toggleSelectAll = () => {
    if (selectedIds.length === floorPlans.length && floorPlans.length > 0) {
      setSelectedIds([]);
    } else {
      setSelectedIds(floorPlans.map((p) => p.id));
    }
  };

  // 표시용 페이지 번호 (1-based)
  const displayPage = currentPage + 1;

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
          <button className={styles.searchBtn} onClick={handleSearch}><FiSearch /> 검색</button>
          <button className={styles.searchResetBtn} onClick={resetFilters}>초기화</button>
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
            </div>
            <div className={styles.filterActions}>
              <button className={styles.resetBtn} onClick={resetFilters}>초기화</button>
              <button className={styles.primaryBtn} onClick={() => handleAdvancedSearch(0)}>검색</button>
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
                    <td>{plan.createdAt ? (() => { const d = new Date(plan.createdAt); return `${d.getFullYear()}.${(d.getMonth()+1).toString().padStart(2,'0')}.${d.getDate().toString().padStart(2,'0')}`; })() : '-'}</td>
                    <td>
                      <div className={styles.actions}>
                        <button className={styles.actionBtn} onClick={() => handleViewDetail(plan.id)}>
                          상세보기
                        </button>
                        <button className={`${styles.actionBtn} ${styles.actionBtnDanger}`} onClick={() => handleDelete(plan.id)}>
                          삭제
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
          <span className={styles.pageInfo}>총 {totalElements}개 도면 (페이지 {displayPage}/{totalPages || 1})</span>
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

      {/* 도면 상세 모달 */}
      {detailPlan && (
        <div className={styles.modalOverlay} onClick={() => setDetailPlan(null)}>
          <div className={styles.detailModal} onClick={(e) => e.stopPropagation()}>
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
            <div className={styles.detailModalBody}>
              {/* 좌측: 이미지 */}
              <div
                ref={imageContainerRef}
                className={styles.detailImageSection}
                onMouseDown={handleMouseDown}
                onMouseMove={handleMouseMove}
                onMouseUp={handleMouseUp}
                onMouseLeave={handleMouseUp}
                style={{ cursor: imageScale > 1 ? (isDragging ? 'grabbing' : 'grab') : 'default' }}
              >
                {detailPlan.imageUrl ? (
                  <img
                    src={detailPlan.imageUrl}
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
                      (e.target as HTMLImageElement).style.display = 'none';
                      const container = (e.target as HTMLImageElement).parentElement;
                      if (container) {
                        container.innerHTML = `
                          <div style="text-align: center; padding: 40px; color: #999;">
                            <div style="font-size: 2rem; margin-bottom: 0.5rem;">🗑️</div>
                            <p>이미지가 삭제되었거나 불러올 수 없습니다.</p>
                          </div>
                        `;
                      }
                    }}
                  />
                ) : (
                  <div style={{ textAlign: 'center', padding: '40px', color: '#999' }}>
                    <p>이미지 URL이 없습니다.</p>
                  </div>
                )}
              </div>

              {/* 우측: 상세 정보 */}
              <div className={styles.detailInfoSection}>
                <div className={styles.detailInfoItem}>
                  <span className={styles.detailLabel}>업로더</span>
                  <span className={styles.detailValue}>{detailPlan.user?.name} ({detailPlan.user?.email})</span>
                </div>
                <div className={styles.detailInfoItem}>
                  <span className={styles.detailLabel}>업로드일</span>
                  <span className={styles.detailValue}>
                    {detailPlan.createdAt ? (() => { const d = new Date(detailPlan.createdAt); return `${d.getFullYear()}.${(d.getMonth()+1).toString().padStart(2,'0')}.${d.getDate().toString().padStart(2,'0')} ${d.getHours().toString().padStart(2,'0')}:${d.getMinutes().toString().padStart(2,'0')}`; })() : '-'}
                  </span>
                </div>
                {detailPlan.assessmentJson && (
                  <div className={styles.detailAssessment}>
                    <span className={styles.detailLabel}>분석 결과</span>
                    <pre className={styles.detailJsonContent}>
                      {(() => {
                        try {
                          return JSON.stringify(JSON.parse(detailPlan.assessmentJson), null, 2);
                        } catch {
                          return detailPlan.assessmentJson;
                        }
                      })()}
                    </pre>
                  </div>
                )}
              </div>
            </div>
          </div>
        </div>
      )}

      {/* 삭제 확인 모달 */}
      {confirmModal && (
        <div className={styles.modalOverlay} onClick={() => setConfirmModal(null)}>
          <div className={styles.confirmModal} onClick={(e) => e.stopPropagation()}>
            <div className={styles.confirmModalHeader}>
              <span className={styles.confirmModalIcon}>⚠️</span>
              <h3>삭제 확인</h3>
            </div>
            <p className={styles.confirmModalMessage}>{confirmModal.message}</p>
            <p className={styles.confirmModalWarning}>이 작업은 되돌릴 수 없습니다.</p>
            <div className={styles.confirmModalActions}>
              <button className={styles.resetBtn} onClick={() => setConfirmModal(null)}>취소</button>
              <button className={styles.dangerBtn} onClick={executeDelete}>삭제</button>
            </div>
          </div>
        </div>
      )}
    </AdminLayout>
  );
}
