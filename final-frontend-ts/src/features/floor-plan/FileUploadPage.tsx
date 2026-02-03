import React, { useState, useEffect, useRef, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import { FiMessageSquare, FiEdit, FiFolder, FiSave, FiX, FiZoomIn } from 'react-icons/fi';
import { AiOutlineLoading3Quarters, AiOutlineHome } from 'react-icons/ai';
import { BiErrorCircle } from 'react-icons/bi';
import { RiRobot2Line } from 'react-icons/ri';
import { useTheme } from '@/shared/contexts/ThemeContext';
import { convertCocoToFloorPlan } from './utils/cocoParser';
import type { CocoData } from './utils/cocoParser';
import { convertTopologyToFloorPlan, isTopologyFormat } from './utils/topologyParser';
import type { TopologyData } from './utils/topologyParser';
import type { AnalysisStatus, FloorPlanUploadResponse, HoverableItem, Bbox } from './types/floor-plan.types';
import { uploadFloorPlan, saveFloorPlan } from './api/floor-plan.api';
import JsonInspector from './components/JsonInspector';
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
  const [topologyGraphUrl, setTopologyGraphUrl] = useState<string | null>(null);

  // 이미지 확대 모달 상태
  const [zoomModalImage, setZoomModalImage] = useState<string | null>(null);
  const [zoomModalTitle, setZoomModalTitle] = useState<string>('');
  const [zoomLevel, setZoomLevel] = useState<number>(1);
  const [panPosition, setPanPosition] = useState<{ x: number; y: number }>({ x: 0, y: 0 });
  const [isPanning, setIsPanning] = useState<boolean>(false);
  const [panStart, setPanStart] = useState<{ x: number; y: number }>({ x: 0, y: 0 });

  // Hover 상태 (그룹화로 인해 배열로 변경)
  const [hoveredItems, setHoveredItems] = useState<HoverableItem[]>([]);

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

  // 이미지 스케일 계산 (실제 렌더링 크기 기준)
  const updateImageScale = useCallback(() => {
    const image = imageRef.current;
    if (!image || !image.naturalWidth) return;

    // 실제 렌더링된 이미지 크기
    const renderedWidth = image.clientWidth;
    const renderedHeight = image.clientHeight;
    const naturalWidth = image.naturalWidth;
    const naturalHeight = image.naturalHeight;

    // 원본 대비 스케일 계산
    const scaleX = renderedWidth / naturalWidth;
    const scaleY = renderedHeight / naturalHeight;

    // 오버레이는 이미지 위에 직접 배치되므로 offset 불필요
    setImageScale({ scaleX, scaleY, offsetX: 0, offsetY: 0 });

    console.log('이미지 스케일 계산:', {
      natural: `${naturalWidth}x${naturalHeight}`,
      rendered: `${renderedWidth}x${renderedHeight}`,
      scale: `${scaleX.toFixed(4)}, ${scaleY.toFixed(4)}`,
    });
  }, []);

  useEffect(() => {
    const image = imageRef.current;
    if (!image) return;

    image.addEventListener('load', updateImageScale);

    // 윈도우 리사이즈 시에도 스케일 재계산
    window.addEventListener('resize', updateImageScale);

    if (image.complete) updateImageScale();

    return () => {
      image.removeEventListener('load', updateImageScale);
      window.removeEventListener('resize', updateImageScale);
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
  // 도면 분석 (백엔드 API 호출 → Python 서버 분석)
  // ============================================
  const startAnalysis = async (file: File) => {
    setAnalysisStatus('analyzing');
    setJsonResult('');
    setAiSummary('');
    setAnalysisResult(null);
    setHoveredItems([]);
    setTopologyGraphUrl(null);

    console.log('=== 도면 분석 시작 ===');
    console.log('파일명:', file.name);

    try {
      // 1. 백엔드 API 호출 (Python 서버에서 실시간 분석)
      console.log('백엔드 API 호출 중...');
      const apiResult = await uploadFloorPlan(file);
      console.log('API 응답:', apiResult);

      // API 응답에서 필요한 데이터 추출
      let result: FloorPlanUploadResponse;

      // 백엔드 응답 형식에 따라 파싱
      // 백엔드 FloorplanPreviewResponse 필드명: topologyJson, topologyImageUrl, analysisDescription
      const topologyData = apiResult.topologyJson || apiResult.elementJson;
      console.log('topologyData 존재 여부:', !!topologyData);
      console.log('topologyData 타입:', typeof topologyData);

      if (topologyData) {
        // 백엔드가 { topologyJson, topologyImageUrl, analysisDescription, embedding } 형태로 반환하는 경우
        const jsonData = typeof topologyData === 'string'
          ? JSON.parse(topologyData)
          : topologyData;

        console.log('파싱된 jsonData:', jsonData);
        console.log('isTopologyFormat:', isTopologyFormat(jsonData));

        if (isTopologyFormat(jsonData)) {
          console.log('Topology 형식으로 변환 시작...');
          result = convertTopologyToFloorPlan(jsonData as TopologyData, file.name);
          console.log('변환된 result.rooms:', result.rooms);
          console.log('변환된 result.structures:', result.structures);
          console.log('변환된 result.objects:', result.objects);
        } else {
          console.log('COCO 형식으로 변환 시작...');
          result = convertCocoToFloorPlan(jsonData as CocoData, file.name);
        }

        // 위상 그래프 이미지가 있으면 설정 (이미 data:image/png;base64 포함된 전체 URL)
        const topologyImageUrl = apiResult.topologyImageUrl || apiResult.topologyImage;
        if (topologyImageUrl) {
          // 이미 data:image/png;base64 형식이면 그대로, 아니면 추가
          if (topologyImageUrl.startsWith('data:')) {
            setTopologyGraphUrl(topologyImageUrl);
          } else {
            setTopologyGraphUrl(`data:image/png;base64,${topologyImageUrl}`);
          }
        }

        // AI 평가가 있으면 설정
        const analysisDescription = apiResult.analysisDescription || apiResult.eval;
        if (analysisDescription) {
          setAiSummary(analysisDescription);
        } else {
          setAiSummary(generateSummary(result));
        }

        // 임베딩 벡터 저장
        if (apiResult.embedding) {
          result.embedding = apiResult.embedding;
        }
      } else if (apiResult.rooms) {
        // 이미 변환된 형태로 반환된 경우
        result = apiResult;
        setAiSummary(generateSummary(result));
      } else {
        // 형식 감지: Topology vs COCO
        if (isTopologyFormat(apiResult)) {
          result = convertTopologyToFloorPlan(apiResult as unknown as TopologyData, file.name);
        } else {
          result = convertCocoToFloorPlan(apiResult as unknown as CocoData, file.name);
        }
        setAiSummary(generateSummary(result));
      }

      console.log('변환 결과:', result);
      setAnalysisResult(result);
      setAnalysisStatus('completed');
      setJsonResult(JSON.stringify(result, null, 2));
      setToastMessage('도면 분석이 완료되었습니다.');

    } catch (apiError) {
      console.error('API 호출 실패:', apiError);
      setAnalysisStatus('error');
      setJsonResult('');
      setToastMessage('도면 분석에 실패했습니다. 서버 연결을 확인하세요.');
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
      // 백엔드에 저장 요청
      const saveData = {
        name: analysisResult.name,
        imageUrl: imageUrl,
        elementJson: analysisResult,
        eval: aiSummary,
        embedding: analysisResult.embedding || null,
      };
      await saveFloorPlan(saveData);
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
    setHoveredItems([]);
    setTopologyGraphUrl(null);
  };

  // 이미지 확대 모달 열기
  const openZoomModal = (imageSrc: string, title: string) => {
    setZoomModalImage(imageSrc);
    setZoomModalTitle(title);
    setZoomLevel(1);
    setPanPosition({ x: 0, y: 0 });
  };

  // 이미지 확대 모달 닫기
  const closeZoomModal = () => {
    setZoomModalImage(null);
    setZoomModalTitle('');
    setZoomLevel(1);
    setPanPosition({ x: 0, y: 0 });
  };

  // 스크롤로 확대/축소
  const handleZoomWheel = (e: React.WheelEvent) => {
    e.preventDefault();
    const delta = e.deltaY > 0 ? -0.1 : 0.1;
    setZoomLevel((prev) => Math.min(Math.max(prev + delta, 0.5), 5));
  };

  // 드래그 시작
  const handlePanStart = (e: React.MouseEvent) => {
    if (zoomLevel > 1) {
      setIsPanning(true);
      setPanStart({ x: e.clientX - panPosition.x, y: e.clientY - panPosition.y });
    }
  };

  // 드래그 중
  const handlePanMove = (e: React.MouseEvent) => {
    if (isPanning && zoomLevel > 1) {
      setPanPosition({
        x: e.clientX - panStart.x,
        y: e.clientY - panStart.y,
      });
    }
  };

  // 드래그 종료
  const handlePanEnd = () => {
    setIsPanning(false);
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
            onDragEnter={handleDrag}
            onDragLeave={handleDrag}
            onDragOver={handleDrag}
            onDrop={handleDrop}
            className={styles.dropZone}
            style={{
              borderColor: dragActive ? colors.primary : colors.border,
              backgroundColor: dragActive ? colors.inputBg : '#FFFFFF',
            }}
          >
            {selectedFile && imageUrl ? (
              <div className={styles.imageWrapper}>
                <div ref={imageContainerRef} className={styles.imageContainer}>
                  <img
                    ref={imageRef}
                    src={imageUrl}
                    alt="도면 미리보기"
                    className={styles.previewImage}
                  />
                  {/* 확대 버튼 */}
                  <button
                    className={styles.zoomButton}
                    onClick={() => openZoomModal(imageUrl, '도면 이미지')}
                    title="확대해서 보기"
                  >
                    <FiZoomIn size={18} />
                  </button>
                  {/* Segmentation Polygon 또는 Bbox Overlay (여러 개 동시 표시) */}
                  {hoveredItems.length > 0 && (
                    <>
                      {/* SVG로 모든 폴리곤 렌더링 */}
                      <svg
                        className={styles.segmentationOverlay}
                        style={{
                          position: 'absolute',
                          top: 0,
                          left: 0,
                          width: '100%',
                          height: '100%',
                          pointerEvents: 'none',
                        }}
                      >
                        {hoveredItems.map((item) =>
                          item.segmentation ? (
                            <g key={`overlay-${item.type}-${item.id}`}>
                              <polygon
                                points={
                                  item.segmentation
                                    .reduce((acc: string[], coord, i, arr) => {
                                      if (i % 2 === 0 && i + 1 < arr.length) {
                                        const x = coord * imageScale.scaleX;
                                        const y = arr[i + 1] * imageScale.scaleY;
                                        acc.push(`${x},${y}`);
                                      }
                                      return acc;
                                    }, [])
                                    .join(' ')
                                }
                                fill={getOverlayColor(item.type).fill}
                                stroke={getOverlayColor(item.type).stroke}
                                strokeWidth="2"
                              />
                              <text
                                x={item.bbox[0] * imageScale.scaleX}
                                y={item.bbox[1] * imageScale.scaleY - 5}
                                fill={getOverlayColor(item.type).stroke}
                                fontSize="12"
                                fontWeight="bold"
                              >
                                {item.name}
                              </text>
                            </g>
                          ) : null
                        )}
                      </svg>
                      {/* Bbox 사각형 (segmentation 없는 아이템용) */}
                      {hoveredItems
                        .filter((item) => !item.segmentation)
                        .map((item) => (
                          <div
                            key={`bbox-${item.type}-${item.id}`}
                            className={styles.bboxOverlay}
                            style={{
                              left: transformBbox(item.bbox).left,
                              top: transformBbox(item.bbox).top,
                              width: transformBbox(item.bbox).width,
                              height: transformBbox(item.bbox).height,
                              backgroundColor: getOverlayColor(item.type).fill,
                              borderColor: getOverlayColor(item.type).stroke,
                            }}
                          >
                            <span
                              className={styles.bboxLabel}
                              style={{ backgroundColor: getOverlayColor(item.type).stroke }}
                            >
                              {item.name}
                            </span>
                          </div>
                        ))}
                    </>
                  )}
                </div>
                <div className={styles.fileInfo}>
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
                topologyGraphUrl ? (
                  <div className={styles.graphImageWrapper}>
                    <img
                      src={topologyGraphUrl}
                      alt="공간 위상 그래프"
                      className={styles.topologyGraphImage}
                    />
                    <button
                      className={styles.zoomButton}
                      onClick={() => openZoomModal(topologyGraphUrl, '공간 위상 그래프')}
                      title="확대해서 보기"
                    >
                      <FiZoomIn size={18} />
                    </button>
                  </div>
                ) : (
                  <div style={{ textAlign: 'center' }}>
                    <div className={styles.statusIcon}><AiOutlineHome size={32} /></div>
                    <p style={{ color: colors.textSecondary, fontSize: '0.875rem' }}>
                      그래프 이미지가 없습니다
                    </p>
                  </div>
                )
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
              분석 결과
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
            {analysisStatus === 'completed' && (
              <JsonInspector
                data={analysisResult}
                onHover={(items) => setHoveredItems(items || [])}
                hoveredItem={hoveredItems[0] || null}
              />
            )}
            {analysisStatus === 'error' && (
              <p className={styles.jsonPlaceholder} style={{ color: colors.error }}>
                분석 결과가 없습니다
              </p>
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

      {/* 이미지 확대 모달 */}
      {zoomModalImage && (
        <div className={styles.zoomModal} onClick={closeZoomModal}>
          <div className={styles.zoomModalContent} onClick={(e) => e.stopPropagation()}>
            <div className={styles.zoomModalHeader}>
              <h3 className={styles.zoomModalTitle}>{zoomModalTitle}</h3>
              <div className={styles.zoomControls}>
                <span className={styles.zoomLevelText}>{Math.round(zoomLevel * 100)}%</span>
                <button
                  className={styles.zoomControlBtn}
                  onClick={() => setZoomLevel((prev) => Math.max(prev - 0.25, 0.5))}
                >
                  -
                </button>
                <button
                  className={styles.zoomControlBtn}
                  onClick={() => setZoomLevel((prev) => Math.min(prev + 0.25, 5))}
                >
                  +
                </button>
              </div>
              <button className={styles.zoomModalClose} onClick={closeZoomModal}>
                <FiX size={24} />
              </button>
            </div>
            <div
              className={styles.zoomModalBody}
              onWheel={handleZoomWheel}
              onMouseDown={handlePanStart}
              onMouseMove={handlePanMove}
              onMouseUp={handlePanEnd}
              onMouseLeave={handlePanEnd}
              style={{ cursor: zoomLevel > 1 ? (isPanning ? 'grabbing' : 'grab') : 'default' }}
            >
              <img
                src={zoomModalImage}
                alt={zoomModalTitle}
                className={styles.zoomModalImage}
                style={{
                  transform: `scale(${zoomLevel}) translate(${panPosition.x / zoomLevel}px, ${panPosition.y / zoomLevel}px)`,
                }}
                draggable={false}
              />
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

export default FileUploadPage;
