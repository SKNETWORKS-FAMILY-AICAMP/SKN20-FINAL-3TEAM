import React, { useState, useEffect, useRef, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import { FiHome, FiMessageSquare, FiEdit, FiFolder, FiSave } from 'react-icons/fi';
import { AiOutlineLoading3Quarters, AiOutlineHome } from 'react-icons/ai';
import { BiErrorCircle } from 'react-icons/bi';
import { RiRobot2Line } from 'react-icons/ri';
import { useTheme } from '@/shared/contexts/ThemeContext';
import { mockFloorPlanResult } from './data/mockData';
import type { AnalysisStatus, FloorPlanUploadResponse, HoverableItem, Bbox } from './types/floor-plan.types';
import styles from './FileUploadPage.module.css';

const FileUploadPage: React.FC = () => {
  const navigate = useNavigate();
  const { colors } = useTheme();
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [imageUrl, setImageUrl] = useState<string | null>(null);
  const [dragActive, setDragActive] = useState(false);
  const [analysisStatus, setAnalysisStatus] = useState<AnalysisStatus>('idle');
  const [analysisResult, setAnalysisResult] = useState<FloorPlanUploadResponse | null>(null);
  const [jsonResult, setJsonResult] = useState<string>('');
  const [aiSummary, setAiSummary] = useState<string>('');
  const [toastMessage, setToastMessage] = useState<string>('');
  const [isSaving, setIsSaving] = useState(false);

  // Hover 상태
  const [hoveredItem, setHoveredItem] = useState<HoverableItem | null>(null);

  // 이미지 스케일 계산용 refs
  const imageContainerRef = useRef<HTMLDivElement>(null);
  const imageRef = useRef<HTMLImageElement>(null);
  const [imageScale, setImageScale] = useState({ scaleX: 1, scaleY: 1, offsetX: 0, offsetY: 0 });

  useEffect(() => {
    if (toastMessage) {
      const timer = setTimeout(() => setToastMessage(''), 3000);
      return () => clearTimeout(timer);
    }
  }, [toastMessage]);

  // 이미지 URL 생성 및 정리
  useEffect(() => {
    if (selectedFile) {
      const url = URL.createObjectURL(selectedFile);
      setImageUrl(url);
      return () => URL.revokeObjectURL(url);
    } else {
      setImageUrl(null);
    }
  }, [selectedFile]);

  // 이미지 스케일 계산
  const updateImageScale = useCallback(() => {
    const container = imageContainerRef.current;
    const image = imageRef.current;
    if (!container || !image || !image.naturalWidth) return;

    const containerWidth = container.clientWidth;
    const containerHeight = container.clientHeight;
    const naturalWidth = image.naturalWidth;
    const naturalHeight = image.naturalHeight;

    const containerRatio = containerWidth / containerHeight;
    const imageRatio = naturalWidth / naturalHeight;

    let renderedWidth: number;
    let renderedHeight: number;

    if (imageRatio > containerRatio) {
      renderedWidth = containerWidth;
      renderedHeight = containerWidth / imageRatio;
    } else {
      renderedHeight = containerHeight;
      renderedWidth = containerHeight * imageRatio;
    }

    const offsetX = (containerWidth - renderedWidth) / 2;
    const offsetY = (containerHeight - renderedHeight) / 2;
    const scaleX = renderedWidth / naturalWidth;
    const scaleY = renderedHeight / naturalHeight;

    setImageScale({ scaleX, scaleY, offsetX, offsetY });
  }, []);

  useEffect(() => {
    const image = imageRef.current;
    const container = imageContainerRef.current;
    if (!image || !container) return;

    image.addEventListener('load', updateImageScale);
    const resizeObserver = new ResizeObserver(updateImageScale);
    resizeObserver.observe(container);

    if (image.complete) updateImageScale();

    return () => {
      image.removeEventListener('load', updateImageScale);
      resizeObserver.disconnect();
    };
  }, [imageUrl, updateImageScale]);

  const handleDrag = (e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    if (e.type === 'dragenter' || e.type === 'dragover') {
      setDragActive(true);
    } else if (e.type === 'dragleave') {
      setDragActive(false);
    }
  };

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    setDragActive(false);

    const files = Array.from(e.dataTransfer.files).filter(
      (file) => file.type === 'image/png' || file.type === 'image/jpeg'
    );
    if (files.length > 0) {
      setSelectedFile(files[0]);
      startAnalysis(files[0]);
    }
  };

  const handleFileSelect = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files.length > 0) {
      const file = e.target.files[0];
      if (file.type === 'image/png' || file.type === 'image/jpeg') {
        setSelectedFile(file);
        startAnalysis(file);
      }
    }
  };

  // ============================================
  // 도면 분석 (Mock 데이터 사용)
  // ============================================
  const startAnalysis = async (_file: File) => {
    setAnalysisStatus('analyzing');
    setJsonResult('');
    setAiSummary('');
    setAnalysisResult(null);
    setHoveredItem(null);

    // Mock: 1.5초 후 결과 반환
    await new Promise((resolve) => setTimeout(resolve, 1500));

    try {
      // TODO: 백엔드 연결 시 아래 주석 해제
      // const result = await uploadFloorPlan(file);

      const result = mockFloorPlanResult;

      setAnalysisResult(result);
      setAnalysisStatus('completed');
      setJsonResult(JSON.stringify(result, null, 2));

      const summary = generateSummary(result);
      setAiSummary(summary);
    } catch (error) {
      console.error('도면 분석 실패:', error);
      setAnalysisStatus('error');
      setJsonResult('');
      setToastMessage('도면 분석에 실패했습니다.');
    }
  };

  const generateSummary = (result: FloorPlanUploadResponse): string => {
    const roomNames = result.rooms.map((r) => r.spcname || r.ocrname).join(', ');
    const structureCount = result.structures?.length || 0;
    const objectCount = result.objects?.length || 0;

    return (
      `이 도면은 총 ${result.roomCount}개의 공간으로 구성된 ${result.totalArea}㎡ 규모의 주거 공간입니다. ` +
      `공간 구성: ${roomNames}. ` +
      `구조물 ${structureCount}개, 객체 ${objectCount}개가 감지되었습니다.`
    );
  };

  const handleSaveToDb = async () => {
    if (!analysisResult) return;

    setIsSaving(true);
    try {
      // TODO: 백엔드 연결 시 실제 API 호출
      await new Promise((resolve) => setTimeout(resolve, 500));
      setToastMessage('DB에 저장되었습니다');
    } catch (error) {
      console.error('저장 실패:', error);
      setToastMessage('저장에 실패했습니다.');
    } finally {
      setIsSaving(false);
    }
  };

  const handleReset = () => {
    setSelectedFile(null);
    setImageUrl(null);
    setAnalysisStatus('idle');
    setAnalysisResult(null);
    setJsonResult('');
    setAiSummary('');
    setHoveredItem(null);
  };

  const renderStatusBadge = () => {
    const statusConfig = {
      idle: { text: '대기중', bg: colors.border, color: colors.textSecondary },
      analyzing: { text: '분석중...', bg: '#FCD34D', color: '#92400E' },
      completed: { text: '완료', bg: '#10B981', color: '#FFFFFF' },
      error: { text: '오류', bg: '#EF4444', color: '#FFFFFF' },
    };
    const config = statusConfig[analysisStatus];

    return (
      <span className={styles.statusBadge} style={{ backgroundColor: config.bg, color: config.color }}>
        {config.text}
      </span>
    );
  };

  // ============================================
  // Bbox 좌표 변환
  // ============================================
  const transformBbox = (bbox: Bbox) => {
    const [x1, y1, x2, y2] = bbox;
    return {
      left: x1 * imageScale.scaleX + imageScale.offsetX,
      top: y1 * imageScale.scaleY + imageScale.offsetY,
      width: (x2 - x1) * imageScale.scaleX,
      height: (y2 - y1) * imageScale.scaleY,
    };
  };

  // ============================================
  // JSON 코드에서 hover 가능한 HTML 생성
  // ============================================
  const renderHoverableJson = () => {
    if (!analysisResult || !jsonResult) return jsonResult;

    // 각 객체 타입별로 hover 영역 생성
    const items: { type: 'room' | 'structure' | 'object'; item: any; startIdx: number; endIdx: number }[] = [];

    // rooms 찾기
    analysisResult.rooms.forEach((room) => {
      const searchStr = `"id": ${room.id},`;
      const idx = jsonResult.indexOf(searchStr);
      if (idx !== -1) {
        // 해당 객체의 시작 { 찾기
        let braceCount = 0;
        let startIdx = idx;
        for (let i = idx; i >= 0; i--) {
          if (jsonResult[i] === '}') braceCount++;
          if (jsonResult[i] === '{') {
            if (braceCount === 0) {
              startIdx = i;
              break;
            }
            braceCount--;
          }
        }
        // 해당 객체의 끝 } 찾기
        braceCount = 0;
        let endIdx = idx;
        for (let i = startIdx; i < jsonResult.length; i++) {
          if (jsonResult[i] === '{') braceCount++;
          if (jsonResult[i] === '}') {
            braceCount--;
            if (braceCount === 0) {
              endIdx = i + 1;
              break;
            }
          }
        }
        items.push({ type: 'room', item: room, startIdx, endIdx });
      }
    });

    // structures 찾기
    (analysisResult.structures || []).forEach((str) => {
      const searchStr = `"id": ${str.id},`;
      const structuresIdx = jsonResult.indexOf('"structures"');
      const idx = jsonResult.indexOf(searchStr, structuresIdx);
      if (idx !== -1 && structuresIdx !== -1) {
        let braceCount = 0;
        let startIdx = idx;
        for (let i = idx; i >= 0; i--) {
          if (jsonResult[i] === '}') braceCount++;
          if (jsonResult[i] === '{') {
            if (braceCount === 0) {
              startIdx = i;
              break;
            }
            braceCount--;
          }
        }
        braceCount = 0;
        let endIdx = idx;
        for (let i = startIdx; i < jsonResult.length; i++) {
          if (jsonResult[i] === '{') braceCount++;
          if (jsonResult[i] === '}') {
            braceCount--;
            if (braceCount === 0) {
              endIdx = i + 1;
              break;
            }
          }
        }
        items.push({ type: 'structure', item: str, startIdx, endIdx });
      }
    });

    // objects 찾기
    (analysisResult.objects || []).forEach((obj) => {
      const searchStr = `"id": ${obj.id},`;
      const objectsIdx = jsonResult.indexOf('"objects"');
      const idx = jsonResult.indexOf(searchStr, objectsIdx);
      if (idx !== -1 && objectsIdx !== -1) {
        let braceCount = 0;
        let startIdx = idx;
        for (let i = idx; i >= 0; i--) {
          if (jsonResult[i] === '}') braceCount++;
          if (jsonResult[i] === '{') {
            if (braceCount === 0) {
              startIdx = i;
              break;
            }
            braceCount--;
          }
        }
        braceCount = 0;
        let endIdx = idx;
        for (let i = startIdx; i < jsonResult.length; i++) {
          if (jsonResult[i] === '{') braceCount++;
          if (jsonResult[i] === '}') {
            braceCount--;
            if (braceCount === 0) {
              endIdx = i + 1;
              break;
            }
          }
        }
        items.push({ type: 'object', item: obj, startIdx, endIdx });
      }
    });

    // 정렬
    items.sort((a, b) => a.startIdx - b.startIdx);

    // HTML 생성
    const parts: React.ReactNode[] = [];
    let lastIdx = 0;

    items.forEach((entry, i) => {
      // 이전 텍스트
      if (entry.startIdx > lastIdx) {
        parts.push(
          <span key={`text-${i}`}>{jsonResult.slice(lastIdx, entry.startIdx)}</span>
        );
      }

      const hoverItem: HoverableItem = {
        id: entry.item.id,
        type: entry.type,
        name: entry.type === 'room' ? (entry.item.spcname || entry.item.ocrname) : entry.item.name,
        bbox: entry.item.bbox,
      };

      const isHovered = hoveredItem?.id === hoverItem.id && hoveredItem?.type === hoverItem.type;
      const colorMap = { room: '#3B82F6', structure: '#F97316', object: '#22C55E' };

      parts.push(
        <span
          key={`item-${entry.type}-${entry.item.id}`}
          className={styles.hoverableJsonItem}
          style={{
            backgroundColor: isHovered ? `${colorMap[entry.type]}20` : 'transparent',
            borderLeft: isHovered ? `3px solid ${colorMap[entry.type]}` : '3px solid transparent',
          }}
          onMouseEnter={() => setHoveredItem(hoverItem)}
          onMouseLeave={() => setHoveredItem(null)}
        >
          {jsonResult.slice(entry.startIdx, entry.endIdx)}
        </span>
      );

      lastIdx = entry.endIdx;
    });

    // 남은 텍스트
    if (lastIdx < jsonResult.length) {
      parts.push(<span key="text-end">{jsonResult.slice(lastIdx)}</span>);
    }

    return parts;
  };

  // Overlay 색상
  const getOverlayColor = (type: string) => {
    const colors = {
      room: { fill: 'rgba(59, 130, 246, 0.3)', stroke: '#3B82F6' },
      structure: { fill: 'rgba(249, 115, 22, 0.3)', stroke: '#F97316' },
      object: { fill: 'rgba(34, 197, 94, 0.3)', stroke: '#22C55E' },
    };
    return colors[type as keyof typeof colors] || colors.room;
  };

  return (
    <div className={styles.container} style={{ backgroundColor: colors.background }}>
      <div
        className={styles.iconSidebar}
        style={{ backgroundColor: colors.sidebarBg, borderRight: `1px solid ${colors.border}` }}
      >
        <div onClick={() => navigate('/')} title="홈" className={styles.iconBtn}>
          <FiHome size={20} />
        </div>
        <div onClick={() => navigate('/main')} title="채팅" className={styles.iconBtn}>
          <FiMessageSquare size={20} />
        </div>
        <div
          title="도면 등록"
          className={styles.iconBtn}
          style={{
            backgroundColor: '#FEF3C7',
            borderLeft: `3px solid ${colors.primary}`,
          }}
        >
          <FiEdit size={20} />
        </div>
      </div>

      <div className={styles.mainContent}>
        {/* 좌측 패널 */}
        <div className={styles.leftPanel} style={{ borderRight: `1px solid ${colors.border}` }}>
          <h1 className={styles.title} style={{ color: colors.textPrimary }}>
            내 도면 등록하기
          </h1>
          <p className={styles.subtitle} style={{ color: colors.textSecondary }}>
            도면 1장을 업로드하면 AI가 자동 분석합니다
          </p>

          {/* 도면 업로드/미리보기 영역 */}
          <div
            ref={imageContainerRef}
            onDragEnter={handleDrag}
            onDragLeave={handleDrag}
            onDragOver={handleDrag}
            onDrop={handleDrop}
            className={styles.dropZone}
            style={{
              borderColor: dragActive ? colors.primary : colors.border,
              backgroundColor: dragActive ? colors.inputBg : '#FFFFFF',
              position: 'relative',
            }}
          >
            {selectedFile && imageUrl ? (
              <div className={styles.imageWrapper}>
                <img
                  ref={imageRef}
                  src={imageUrl}
                  alt="도면 미리보기"
                  className={styles.previewImage}
                />
                {/* Bbox Overlay */}
                {hoveredItem && (
                  <div
                    className={styles.bboxOverlay}
                    style={{
                      left: transformBbox(hoveredItem.bbox).left,
                      top: transformBbox(hoveredItem.bbox).top,
                      width: transformBbox(hoveredItem.bbox).width,
                      height: transformBbox(hoveredItem.bbox).height,
                      backgroundColor: getOverlayColor(hoveredItem.type).fill,
                      borderColor: getOverlayColor(hoveredItem.type).stroke,
                    }}
                  >
                    <span
                      className={styles.bboxLabel}
                      style={{ backgroundColor: getOverlayColor(hoveredItem.type).stroke }}
                    >
                      {hoveredItem.name}
                    </span>
                  </div>
                )}
                <p className={styles.fileName} style={{ color: colors.textPrimary }}>
                  {selectedFile.name}
                </p>
                <button
                  onClick={handleReset}
                  className={styles.resetBtn}
                  style={{ border: `1px solid ${colors.border}`, color: colors.textSecondary }}
                >
                  다른 파일 선택
                </button>
              </div>
            ) : (
              <>
                <div className={styles.dropIcon}><FiFolder size={48} /></div>
                <p className={styles.dropText} style={{ color: colors.textPrimary }}>
                  도면 이미지를 끌어다 놓으세요
                </p>
                <p className={styles.dropOr} style={{ color: colors.textSecondary }}>
                  또는
                </p>
                <label htmlFor="file-input">
                  <div className={styles.selectBtn} style={{ backgroundColor: colors.primary }}>
                    파일 선택
                  </div>
                </label>
                <input
                  type="file"
                  id="file-input"
                  accept=".jpg,.jpeg,.png"
                  onChange={handleFileSelect}
                  style={{ display: 'none' }}
                />
                <p className={styles.supportText} style={{ color: colors.textSecondary }}>
                  지원 형식: JPG, PNG
                </p>
              </>
            )}
          </div>

          {/* 공간 위상 그래프 */}
          <div
            className={styles.graphSection}
            style={{
              backgroundColor: '#FFFFFF',
              border: `1px solid ${colors.border}`,
            }}
          >
            <h3 className={styles.graphTitle} style={{ color: colors.textPrimary }}>
              공간 위상 그래프
            </h3>
            <div
              className={styles.graphContent}
              style={{ backgroundColor: '#F9FAFB' }}
            >
              {analysisStatus === 'idle' && (
                <p className={styles.statusText} style={{ color: colors.textSecondary }}>
                  도면을 업로드하면 그래프가 표시됩니다
                </p>
              )}
              {analysisStatus === 'analyzing' && (
                <div style={{ textAlign: 'center' }}>
                  <div className={styles.statusIcon}><AiOutlineLoading3Quarters size={32} className={styles.spinIcon} /></div>
                  <p className={styles.statusText} style={{ color: colors.textSecondary }}>
                    분석 중...
                  </p>
                </div>
              )}
              {analysisStatus === 'completed' && (
                <div style={{ textAlign: 'center' }}>
                  <div className={styles.statusIcon}><AiOutlineHome size={32} /></div>
                  <p style={{ color: colors.textSecondary, fontSize: '0.875rem' }}>
                    그래프 시각화 영역<br />(CV 연동 후 렌더링 예정)
                  </p>
                </div>
              )}
              {analysisStatus === 'error' && (
                <div style={{ textAlign: 'center' }}>
                  <div className={styles.statusIcon}><BiErrorCircle size={32} color="#EF4444" /></div>
                  <p className={styles.statusText} style={{ color: colors.error }}>
                    분석에 실패했습니다
                  </p>
                </div>
              )}
            </div>
          </div>

          {/* 요약 카드 */}
          {analysisStatus === 'completed' && analysisResult && (
            <div className={styles.summaryGrid}>
              <div className={styles.summaryCard} style={{ backgroundColor: '#FFFFFF', border: `1px solid ${colors.border}` }}>
                <p className={styles.summaryLabel} style={{ color: colors.textSecondary }}>총 공간</p>
                <p className={styles.summaryValue} style={{ color: colors.textPrimary }}>{analysisResult.roomCount}개</p>
              </div>
              <div className={styles.summaryCard} style={{ backgroundColor: '#FFFFFF', border: `1px solid ${colors.border}` }}>
                <p className={styles.summaryLabel} style={{ color: colors.textSecondary }}>총 면적</p>
                <p className={styles.summaryValue} style={{ color: colors.textPrimary }}>{analysisResult.totalArea}㎡</p>
              </div>
              <div className={styles.summaryCard} style={{ backgroundColor: '#FFFFFF', border: `1px solid ${colors.border}` }}>
                <p className={styles.summaryLabel} style={{ color: colors.textSecondary }}>구조물/객체</p>
                <p className={styles.summaryValue} style={{ color: colors.textPrimary }}>
                  {(analysisResult.structures?.length || 0) + (analysisResult.objects?.length || 0)}개
                </p>
              </div>
            </div>
          )}
        </div>

        {/* 우측 패널: JSON 코드 */}
        <div className={styles.rightPanel} style={{ backgroundColor: '#F9FAFB' }}>
          <div className={styles.jsonHeader}>
            <h2 className={styles.jsonTitle} style={{ color: colors.textPrimary }}>
              분석 결과 (JSON)
            </h2>
            {renderStatusBadge()}
          </div>

          <div
            className={styles.jsonViewer}
            style={{
              backgroundColor: '#FFFFFF',
              border: `1px solid ${colors.border}`,
            }}
          >
            {analysisStatus === 'idle' && (
              <p className={styles.jsonPlaceholder} style={{ color: colors.textSecondary }}>
                도면을 업로드하면 분석 결과가 표시됩니다
              </p>
            )}
            {analysisStatus === 'analyzing' && (
              <div style={{ marginTop: '2rem' }}>
                <div className={styles.skeleton} style={{ backgroundColor: colors.border }} />
                <div className={`${styles.skeleton} ${styles.skeleton80}`} style={{ backgroundColor: colors.border }} />
                <div className={`${styles.skeleton} ${styles.skeleton60}`} style={{ backgroundColor: colors.border }} />
              </div>
            )}
            {(analysisStatus === 'completed' || analysisStatus === 'error') && (
              <pre className={styles.jsonPre} style={{ color: colors.textPrimary }}>
                {analysisStatus === 'completed' ? renderHoverableJson() : '분석 결과가 없습니다'}
              </pre>
            )}
          </div>

          {analysisStatus === 'completed' && (
            <div
              className={styles.aiSummaryBox}
              style={{
                backgroundColor: '#F0FDF4',
                border: '1px solid #86EFAC',
              }}
            >
              <div className={styles.aiSummaryHeader}>
                <RiRobot2Line size={18} style={{ color: '#10B981' }} />
                <span className={styles.aiSummaryTitle} style={{ color: colors.textPrimary }}>AI 요약</span>
              </div>
              <p className={styles.aiSummaryText} style={{ color: colors.textSecondary }}>
                {aiSummary}
              </p>
            </div>
          )}

          <div className={styles.buttonGroup}>
            <button
              onClick={handleSaveToDb}
              disabled={analysisStatus !== 'completed' || isSaving}
              className={styles.actionBtn}
              style={{
                backgroundColor: analysisStatus === 'completed' && !isSaving ? '#10B981' : colors.border,
                color: analysisStatus === 'completed' && !isSaving ? '#FFFFFF' : colors.textSecondary,
                cursor: analysisStatus === 'completed' && !isSaving ? 'pointer' : 'not-allowed',
              }}
            >
              <FiSave size={16} style={{ marginRight: '0.5rem' }} />
              {isSaving ? '저장 중...' : '저장하기'}
            </button>
          </div>
        </div>
      </div>

      {toastMessage && <div className={styles.toast}>{toastMessage}</div>}
    </div>
  );
};

export default FileUploadPage;
