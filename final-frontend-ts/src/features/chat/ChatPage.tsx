import React, { useState, useRef, useEffect, useCallback } from 'react';
import { useSearchParams } from 'react-router-dom';
import { IoSend, IoImageOutline, IoCloseCircle } from 'react-icons/io5';
import { useTheme } from '@/shared/contexts/ThemeContext';
import { BASE_URL } from '@/shared/api/axios';
import Logo from '@/shared/components/Logo/Logo';
import AppSidebar from '@/shared/components/AppSidebar/AppSidebar';
import ChatMessage from './ChatMessage';
import {
  getChatRooms,
  getRoomHistory,
  sendChat,
  deleteRoom,
  editRoomName,
  deleteAllRooms,
} from './api/chat.api';
import type {
  ChatSession,
  ChatMessage as ChatMessageType,
  ChatRoom,
  ChatHistory,
} from './types/chat.types';
import styles from './ChatPage.module.css';

// ============================================
// 로딩 메시지 (시간 구간별 랜덤)
// ============================================
const LOADING_MESSAGES: { maxSeconds: number; messages: string[] }[] = [
  {
    maxSeconds: 30,
    messages: [
      '요청하신 내용을 분석하고 있어요. 잠시만 기다려 주세요!',
      '관련 자료를 꼼꼼하게 살펴보고 있습니다.',
      '최적의 답변을 드리기 위해 데이터를 확인 중이에요.',
      '열심히 확인하고 있어요. 조금만 기다려 주세요!',
    ],
  },
  {
    maxSeconds: 60,
    messages: [
      '더 정확한 결과를 위해 심층 분석 중이에요.',
      '자료를 하나하나 대조하며 확인하고 있습니다.',
      '꼼꼼하게 확인하고 있어요. 조금만 기다려 주세요!',
      '답변을 정리하고 있습니다. 거의 다 됐어요!',
    ],
  },
  {
    maxSeconds: Infinity,
    messages: [
      '내용이 많아 시간이 조금 걸리고 있어요. 곧 완료됩니다!',
      '최상의 결과를 위해 마지막 검증을 진행하고 있어요.',
      '거의 완료되었습니다. 잠시만요!',
      '결과를 마무리하고 있습니다. 곧 보여드릴게요!',
    ],
  },
];

const getLoadingMessage = (elapsedSeconds: number): string => {
  const bracket = LOADING_MESSAGES.find((b) => elapsedSeconds < b.maxSeconds)!;
  return bracket.messages[Math.floor(Math.random() * bracket.messages.length)];
};

// ============================================
// 도면 답변 파싱: 요약 + 개별 설명 분리
// ============================================
const parseFloorplanAnswer = (answer: string) => {
  // "### [도면 #N]" 또는 "[도면 #N]" 기준으로 분리
  const markerRegex = /(?:#{1,6}\s*)?\[도면 #\d+\]/;
  const splitRegex = /(?:#{1,6}\s*)?\[도면 #\d+\]/;
  const firstMarker = answer.search(markerRegex);

  // [도면 #N] 마커가 없는 경우 (단일 도면 검색 응답)
  // → 전체 답변을 첫 번째 도면의 description으로 사용
  if (firstMarker === -1) {
    return { summary: '', descriptions: [answer.trim()] };
  }

  const summary = firstMarker > 0 ? answer.substring(0, firstMarker).trim() : '';
  const parts = answer.split(splitRegex);
  // parts[0] = 요약, parts[1~] = 각 도면 설명
  const descriptions = parts.slice(1).map((part) =>
    part.replace(/^---\s*/gm, '').replace(/\s*---\s*$/gm, '').trim()
  );
  return { summary, descriptions };
};

// ============================================
// API 타입 → UI 타입 변환 함수
// ============================================
const convertRoomToSession = (room: ChatRoom): ChatSession => ({
  id: String(room.id),
  title: room.name || '새로운 채팅',
  messages: [],
  createdAt: new Date(room.createdAt),
});

const convertHistoryToMessages = (history: ChatHistory[]): ChatMessageType[] => {
  const messages: ChatMessageType[] = [];

  history.forEach((item) => {
    // 질문 (user)
    messages.push({
      id: `${item.id}-q`,
      role: 'user',
      content: item.question,
      timestamp: new Date(item.createdAt),
    });

    // imageUrls JSON 파싱 → 이미지 복원
    let images = undefined;
    let displayContent = item.answer;

    if (item.imageUrls) {
      try {
        const urls: string[] = JSON.parse(item.imageUrls);
        const hasFloorplanMarkers = /(?:#{1,6}\s*)?\[도면 #\d+\]/.test(item.answer);

        if (hasFloorplanMarkers) {
          // 텍스트 검색 모드
          const { summary, descriptions } = parseFloorplanAnswer(item.answer);
          images = urls.map((url, idx) => {
            const fileName = url.split('/').pop() || '';
            const docId = fileName.replace(/\.[^.]+$/, '');
            return {
              url: url.startsWith('http') ? url : `${BASE_URL}${url}`,
              name: docId || `도면 #${idx + 1}`,
              description: descriptions[idx] || '',
            };
          });
          const shownCount = urls.length;
          const totalMatch = summary.match(/(\d+)/);
          const totalCount = totalMatch ? parseInt(totalMatch[1]) : shownCount;
          if (totalCount > shownCount) {
            displayContent = `조건을 만족하는 도면은 총 ${totalCount}개입니다. 그 중 가장 유사한 ${shownCount}개의 도면을 보여드립니다. 더 보고 싶으시면 말씀해주세요!`;
          } else {
            displayContent = `조건을 만족하는 도면 ${totalCount}개를 모두 보여드립니다.`;
          }
        } else {
          // 이미지 분석 모드: [유사 도면 #N] 마커 파싱
          // 마커 형식: "### [유사 도면 #1] APT_FP_OBJ_123" (### prefix + document_id suffix)
          const similarDetectRegex = /(?:#{1,6}\s*)?\[유사 도면 #\d+\]/;
          const similarSplitRegex = /(?:#{1,6}\s*)?\[유사 도면 #\d+\][^\n]*/;
          const firstSimilarIdx = item.answer.search(similarDetectRegex);

          let analysisPart = item.answer;
          let similarDescriptions: string[] = [];

          if (firstSimilarIdx !== -1) {
            analysisPart = item.answer.substring(0, firstSimilarIdx).trim();
            const similarPart = item.answer.substring(firstSimilarIdx);
            const parts = similarPart.split(similarSplitRegex);
            similarDescriptions = parts.slice(1).map((p) => p.trim());
          }

          const totalMatch = analysisPart.match(/유사 도면 (\d+)개\s*$/);
          const shownCount = urls.length;
          const totalCount = totalMatch ? parseInt(totalMatch[1]) : shownCount;
          analysisPart = analysisPart.replace(/\n*유사 도면 \d+개\s*$/, '').trim();

          displayContent = analysisPart;
          if (totalCount > shownCount) {
            displayContent += `\n\n유사한 도면은 총 ${totalCount}개입니다. 그 중 가장 유사한 ${shownCount}개의 도면을 보여드립니다. 더 보고 싶으시면 말씀해주세요!`;
          } else if (shownCount > 0) {
            displayContent += `\n\n유사한 도면 ${shownCount}개를 찾았습니다.`;
          }

          images = urls.map((url, idx) => {
            const fileName = url.split('/').pop() || '';
            const docId = fileName.replace(/\.[^.]+$/, '');
            return {
              url: url.startsWith('http') ? url : `${BASE_URL}${url}`,
              name: docId || `유사 도면 #${idx + 1}`,
              description: similarDescriptions[idx] || '',
            };
          });
        }
      } catch (e) {
        console.error('imageUrls 파싱 실패:', e);
      }
    }

    // 답변 (assistant)
    messages.push({
      id: `${item.id}-a`,
      role: 'assistant',
      content: displayContent,
      timestamp: new Date(item.createdAt),
      images,
    });
  });

  return messages;
};

// ============================================
// ChatPage Component
// ============================================
const ChatPage: React.FC = () => {
  const { colors } = useTheme();
  const [searchParams, setSearchParams] = useSearchParams();

  // 상태
  const [sessions, setSessions] = useState<ChatSession[]>([]);
  const [currentRoomId, setCurrentRoomId] = useState<number | null>(null);
  const [messages, setMessages] = useState<ChatMessageType[]>([]);
  const [inputMessage, setInputMessage] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [isSending, setIsSending] = useState(false);

  const [loadingMessage, setLoadingMessage] = useState('');
  const [selectedImage, setSelectedImage] = useState<File | null>(null);
  const [imagePreview, setImagePreview] = useState<string | null>(null);

  const messagesEndRef = useRef<HTMLDivElement>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const skipLoadHistoryRef = useRef(false); // 새 채팅방 생성 시 히스토리 로드 스킵용

  // ============================================
  // 채팅방 목록 로드
  // ============================================
  const loadChatRooms = useCallback(async () => {
    try {
      setIsLoading(true);
      const rooms = await getChatRooms();
      const convertedSessions = rooms.map(convertRoomToSession);
      // 최신순 정렬 (id가 큰 것이 최신)
      convertedSessions.sort((a, b) => parseInt(b.id) - parseInt(a.id));
      setSessions(convertedSessions);
      // 채팅방 자동 선택 안 함 - 빈 화면으로 시작
    } catch (error) {
      console.error('채팅방 목록 로드 실패:', error);
    } finally {
      setIsLoading(false);
    }
  }, []);

  // ============================================
  // 채팅 기록 로드
  // ============================================
  const loadChatHistory = useCallback(async (roomId: number) => {
    try {
      setIsLoading(true);
      const history = await getRoomHistory({ chatRoomId: roomId });
      const convertedMessages = convertHistoryToMessages(history);
      setMessages(convertedMessages);
    } catch (error) {
      console.error('채팅 기록 로드 실패:', error);
      setMessages([]);
    } finally {
      setIsLoading(false);
    }
  }, []);

  // ============================================
  // 초기 로드
  // ============================================
  useEffect(() => {
    const init = async () => {
      await loadChatRooms();
      const roomIdParam = searchParams.get('roomId');
      if (roomIdParam) {
        setCurrentRoomId(Number(roomIdParam));
        setSearchParams({}, { replace: true });
      }
    };
    init();
  }, []);

  // ============================================
  // 방 선택 시 기록 로드
  // ============================================
  useEffect(() => {
    if (currentRoomId !== null) {
      // 새 채팅방 생성 직후에는 히스토리 로드 스킵
      if (skipLoadHistoryRef.current) {
        skipLoadHistoryRef.current = false;
        return;
      }
      loadChatHistory(currentRoomId);
    } else {
      setMessages([]);
    }
  }, [currentRoomId, loadChatHistory]);

  // ============================================
  // 스크롤
  // ============================================
  const prevMessageCountRef = useRef(0);

  const scrollToBottom = (instant = false) => {
    messagesEndRef.current?.scrollIntoView({
      behavior: instant ? 'instant' : 'smooth',
    });
  };

  useEffect(() => {
    const prevCount = prevMessageCountRef.current;
    const currCount = messages.length;
    // 메시지가 1~2개만 늘었으면 smooth, 그 외(채팅방 전환/초기로드)는 instant
    const isNewMessage = prevCount > 0 && currCount - prevCount <= 2;
    scrollToBottom(!isNewMessage);
    prevMessageCountRef.current = currCount;
  }, [messages]);

  // ============================================
  // 로딩 메시지 타이머
  // ============================================
  useEffect(() => {
    if (!isSending) {
      setLoadingMessage('');
      return;
    }

    const startTime = Date.now();
    setLoadingMessage(getLoadingMessage(0));

    const interval = setInterval(() => {
      const elapsed = (Date.now() - startTime) / 1000;
      setLoadingMessage(getLoadingMessage(elapsed));
    }, 4000);

    return () => clearInterval(interval);
  }, [isSending]);

  // ============================================
  // 새 채팅
  // ============================================
  const handleNewChat = () => {
    setCurrentRoomId(null);
    setMessages([]);
  };

  // ============================================
  // 세션 클릭
  // ============================================
  const handleSessionClick = (sessionId: string) => {
    setCurrentRoomId(Number(sessionId));
  };

  // ============================================
  // 채팅방 삭제
  // ============================================
  const handleDeleteSession = async (sessionId: string) => {
    if (!window.confirm('이 채팅방을 삭제하시겠습니까?')) return;

    try {
      await deleteRoom({ chatRoomId: Number(sessionId) });

      const updatedSessions = sessions.filter((s) => s.id !== sessionId);
      setSessions(updatedSessions);

      if (String(currentRoomId) === sessionId) {
        if (updatedSessions.length > 0) {
          setCurrentRoomId(Number(updatedSessions[0].id));
        } else {
          setCurrentRoomId(null);
          setMessages([]);
        }
      }
    } catch (error) {
      console.error('채팅방 삭제 실패:', error);
      alert('채팅방 삭제에 실패했습니다.');
    }
  };

  // ============================================
  // 전체 삭제
  // ============================================
  const handleClearAll = async () => {
    if (!window.confirm('모든 채팅을 삭제하시겠습니까?')) return;

    try {
      await deleteAllRooms();
      setSessions([]);
      setCurrentRoomId(null);
      setMessages([]);
    } catch (error) {
      console.error('전체 삭제 실패:', error);
      alert('전체 삭제에 실패했습니다.');
    }
  };

  // ============================================
  // 채팅방 이름 수정
  // ============================================
  const handleRenameSession = async (sessionId: string, newName: string) => {
    try {
      await editRoomName({ chatRoomId: Number(sessionId), newName });

      setSessions((prev) =>
        prev.map((session) =>
          session.id === sessionId ? { ...session, title: newName } : session
        )
      );
    } catch (error) {
      console.error('이름 수정 실패:', error);
      alert('이름 수정에 실패했습니다.');
    }
  };

  // ============================================
  // 이미지 핸들러
  // ============================================
  const handleImageSelect = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;

    if (!['image/png', 'image/jpeg'].includes(file.type)) {
      alert('PNG 또는 JPG 이미지만 업로드할 수 있습니다.');
      return;
    }

    if (file.size > 50 * 1024 * 1024) {
      alert('이미지 크기는 50MB 이하여야 합니다.');
      return;
    }

    setSelectedImage(file);
    setImagePreview(URL.createObjectURL(file));
  };

  const handleRemoveImage = () => {
    setSelectedImage(null);
    if (imagePreview) {
      URL.revokeObjectURL(imagePreview);
    }
    setImagePreview(null);
    if (fileInputRef.current) {
      fileInputRef.current.value = '';
    }
  };

  const handleImageButtonClick = () => {
    fileInputRef.current?.click();
  };

  // ============================================
  // 메시지 전송
  // ============================================
  const handleSendMessage = async (e: React.FormEvent) => {
    e.preventDefault();
    if ((!inputMessage.trim() && !selectedImage) || isSending) return;

    const question = inputMessage.trim() || (selectedImage ? '이 도면을 분석해주세요' : '');
    setInputMessage('');
    setIsSending(true);

    // 사용자 메시지 즉시 표시
    const userMessage: ChatMessageType = {
      id: `temp-user-${Date.now()}`,
      role: 'user',
      content: question,
      timestamp: new Date(),
      images: selectedImage ? [{
        url: imagePreview || '',
        name: selectedImage.name,
        description: '업로드한 도면 이미지',
      }] : undefined,
    };
    setMessages((prev) => [...prev, userMessage]);

    // 이미지 상태 초기화 (blob URL은 유지 - 메시지에서 사용 중)
    const imageToSend = selectedImage;
    const imagePreviewToRevoke = imagePreview;
    setSelectedImage(null);
    setImagePreview(null);
    if (fileInputRef.current) {
      fileInputRef.current.value = '';
    }

    try {
      // API 호출
      const response = await sendChat({
        chatRoomId: currentRoomId,
        question,
        image: imageToSend || undefined,
      });

      const isNewRoom = currentRoomId === null;

      // AI 응답 즉시 표시 (image_urls가 있으면 도면 이미지 포함)
      const hasFloorplans = response.image_urls && response.image_urls.length > 0;
      let floorplanImages = undefined;
      let displayContent = response.answer;

      if (hasFloorplans) {
        const hasFloorplanMarkers = /(?:#{1,6}\s*)?\[도면 #\d+\]/.test(response.answer);

        if (hasFloorplanMarkers) {
          // 텍스트 검색 모드: [도면 #N] 마커 기반 파싱
          const { summary, descriptions } = parseFloorplanAnswer(response.answer);
          floorplanImages = response.image_urls!.map((url, idx) => {
            const fileName = url.split('/').pop() || '';
            const docId = fileName.replace(/\.[^.]+$/, '');
            return {
              url: url.startsWith('http') ? url : `${BASE_URL}${url}`,
              name: docId || `도면 #${idx + 1}`,
              description: descriptions[idx] || '',
            };
          });
          const shownCount = response.image_urls!.length;
          const totalMatch = summary.match(/(\d+)/);
          const totalCount = totalMatch ? parseInt(totalMatch[1]) : shownCount;
          if (totalCount > shownCount) {
            displayContent = `조건을 만족하는 도면은 총 ${totalCount}개입니다. 그 중 가장 유사한 ${shownCount}개의 도면을 보여드립니다. 더 보고 싶으시면 말씀해주세요!`;
          } else {
            displayContent = `조건을 만족하는 도면 ${totalCount}개를 모두 보여드립니다.`;
          }
        } else {
          // 이미지 분석 모드: [유사 도면 #N] 마커 파싱
          // 마커 형식: "### [유사 도면 #1] APT_FP_OBJ_123" (### prefix + document_id suffix)
          const similarDetectRegex = /(?:#{1,6}\s*)?\[유사 도면 #\d+\]/;
          const similarSplitRegex = /(?:#{1,6}\s*)?\[유사 도면 #\d+\][^\n]*/;
          const firstSimilarIdx = response.answer.search(similarDetectRegex);

          let analysisPart = response.answer;
          let similarDescriptions: string[] = [];

          if (firstSimilarIdx !== -1) {
            analysisPart = response.answer.substring(0, firstSimilarIdx).trim();
            const similarPart = response.answer.substring(firstSimilarIdx);
            const parts = similarPart.split(similarSplitRegex);
            similarDescriptions = parts.slice(1).map((p) => p.trim());
          }

          // "유사 도면 N개" 줄에서 총 개수 추출 후 제거
          const totalMatch = analysisPart.match(/유사 도면 (\d+)개\s*$/);
          const shownCount = response.image_urls!.length;
          const totalCount = totalMatch ? parseInt(totalMatch[1]) : shownCount;
          analysisPart = analysisPart.replace(/\n*유사 도면 \d+개\s*$/, '').trim();

          // displayContent: 분석 텍스트 + 유사 도면 안내 문구
          displayContent = analysisPart;
          if (totalCount > shownCount) {
            displayContent += `\n\n유사한 도면은 총 ${totalCount}개입니다. 그 중 가장 유사한 ${shownCount}개의 도면을 보여드립니다. 더 보고 싶으시면 말씀해주세요!`;
          } else if (shownCount > 0) {
            displayContent += `\n\n유사한 도면 ${shownCount}개를 찾았습니다.`;
          }

          floorplanImages = response.image_urls!.map((url, idx) => {
            const fileName = url.split('/').pop() || '';
            const docId = fileName.replace(/\.[^.]+$/, '');
            return {
              url: url.startsWith('http') ? url : `${BASE_URL}${url}`,
              name: docId || `유사 도면 #${idx + 1}`,
              description: similarDescriptions[idx] || '',
            };
          });
        }
      }

      const aiMessage: ChatMessageType = {
        id: `temp-ai-${Date.now()}`,
        role: 'assistant',
        content: displayContent,
        timestamp: new Date(),
        images: hasFloorplans ? floorplanImages : undefined,
      };
      setMessages((prev) => [...prev, aiMessage]);

      // 새 채팅방이면 세션 목록에 추가하고 현재 방 ID 설정
      if (isNewRoom) {
        const newSession: ChatSession = {
          id: String(response.chatRoomId),
          title: question.slice(0, 30),
          messages: [],
          createdAt: new Date(),
        };
        setSessions((prev) => [newSession, ...prev]);
        
        // 새 채팅방이므로 useEffect에서 히스토리 로드 스킵
        skipLoadHistoryRef.current = true;
        setCurrentRoomId(response.chatRoomId);
      }

    } catch (error) {
      console.error('메시지 전송 실패:', error);

      // 에러 메시지 표시
      const errorMessage: ChatMessageType = {
        id: `error-${Date.now()}`,
        role: 'assistant',
        content: '죄송합니다. 메시지 전송에 실패했습니다. 다시 시도해주세요.',
        timestamp: new Date(),
      };
      setMessages((prev) => [...prev, errorMessage]);
    } finally {
      setIsSending(false);
      if (imagePreviewToRevoke) {
        URL.revokeObjectURL(imagePreviewToRevoke);
      }
    }
  };

  // ============================================
  // 현재 세션 ID (사이드바용)
  // ============================================
  const currentSessionId = currentRoomId !== null ? String(currentRoomId) : '';

  return (
    <div className={styles.container}>
      <AppSidebar
        sessions={sessions}
        currentSessionId={currentSessionId}
        onSessionClick={handleSessionClick}
        onNewChat={handleNewChat}
        onDeleteSession={handleDeleteSession}
        onRenameSession={handleRenameSession}
        onClearAll={handleClearAll}
      />

      <div className={styles.mainArea} style={{ backgroundColor: colors.background }}>
        <div className={styles.messagesArea}>
          {isLoading ? (
            <div className={styles.emptyState}>
              <p style={{ color: colors.textSecondary }}>로딩 중...</p>
            </div>
          ) : messages.length === 0 ? (
            <div className={styles.emptyState}>
              <Logo size={140} />
              <h2 className={styles.emptyTitle} style={{ color: colors.textPrimary }}>
                무엇이든 물어보세요
              </h2>
              <div className={styles.emptyExamples}>
                <p className={styles.emptyExampleLabel} style={{ color: colors.textSecondary }}>사용 예시</p>
                <div className={styles.emptyExampleItem} style={{ backgroundColor: colors.inputBg, color: colors.textSecondary }}>
                  💬 "3Bay 판상형이고, 거실 비율 25% 이상이고 LDK가 넓은 평면 찾아줘"
                </div>
                <div className={styles.emptyExampleItem} style={{ backgroundColor: colors.inputBg, color: colors.textSecondary }}>
                  💬 "(도면이미지 첨부) 이 도면 분석해줘"
                </div>
                <div className={styles.emptyExampleItem} style={{ backgroundColor: colors.inputBg, color: colors.textSecondary }}>
                  💬 "서울특별시 도봉구 방학동 645-28 필지 정보 알려줘"
                </div>
                <div className={styles.emptyExampleItem} style={{ backgroundColor: colors.inputBg, color: colors.textSecondary }}>
                  💬 "경기도 수원시 팔달구에서 공장 건축 가능해?"
                </div>
              </div>
            </div>
          ) : (
            <div>
              {messages.map((message) => (
                <ChatMessage key={message.id} message={message} />
              ))}
              {isSending && (
                <div className={styles.thinkingMessage}>
                  <div className={styles.thinkingBubble}>
                    <span className={styles.thinkingDots}>
                      <span>.</span><span>.</span><span>.</span>
                    </span>
                    <span>{loadingMessage}</span>
                  </div>
                </div>
              )}
              <div ref={messagesEndRef} />
            </div>
          )}
        </div>

        <div
          className={styles.inputArea}
          style={{
            backgroundColor: '#FFFFFF',
            borderTop: `1px solid ${colors.border}`,
          }}
        >
          {/* 이미지 미리보기 */}
          {imagePreview && (
            <div className={styles.imagePreviewContainer}>
              <div className={styles.imagePreviewWrapper}>
                <img
                  src={imagePreview}
                  alt="선택된 도면"
                  className={styles.imagePreviewThumb}
                />
                <button
                  type="button"
                  className={styles.imageRemoveButton}
                  onClick={handleRemoveImage}
                >
                  <IoCloseCircle size={20} />
                </button>
                <span className={styles.imageFileName}>
                  {selectedImage?.name}
                </span>
              </div>
            </div>
          )}

          <form onSubmit={handleSendMessage} className={styles.inputForm}>
            {/* 숨겨진 파일 input */}
            <input
              type="file"
              ref={fileInputRef}
              accept="image/png,image/jpeg"
              onChange={handleImageSelect}
              style={{ display: 'none' }}
            />

            {/* 이미지 첨부 버튼 */}
            <button
              type="button"
              className={styles.imageUploadButton}
              onClick={handleImageButtonClick}
              disabled={isSending}
              style={{ color: selectedImage ? colors.primary : colors.textSecondary }}
            >
              <IoImageOutline size={22} />
            </button>

            <input
              type="text"
              placeholder={selectedImage ? "도면에 대한 질문을 입력하세요..." : "메시지를 입력하세요..."}
              value={inputMessage}
              onChange={(e) => setInputMessage(e.target.value)}
              disabled={isSending}
              className={styles.input}
              style={{
                border: `1px solid ${colors.border}`,
                backgroundColor: colors.inputBg,
                color: colors.textPrimary,
              }}
            />
            <button
              type="submit"
              disabled={isSending || (!inputMessage.trim() && !selectedImage)}
              className={styles.sendButton}
              style={{
                backgroundColor: (isSending || (!inputMessage.trim() && !selectedImage))
                  ? colors.textSecondary
                  : colors.primary,
              }}
            >
              <IoSend size={18} color="#fff" />
            </button>
          </form>
        </div>
      </div>
    </div>
  );
};

export default ChatPage;
