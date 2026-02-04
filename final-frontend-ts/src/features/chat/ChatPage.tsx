import React, { useState, useRef, useEffect, useCallback } from 'react';
import { IoSend } from 'react-icons/io5';
import { useTheme } from '@/shared/contexts/ThemeContext';
import Logo from '@/shared/components/Logo/Logo';
import ChatSidebar from './ChatSidebar';
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
    // 답변 (assistant)
    messages.push({
      id: `${item.id}-a`,
      role: 'assistant',
      content: item.answer,
      timestamp: new Date(item.createdAt),
    });
  });

  return messages;
};

// ============================================
// ChatPage Component
// ============================================
const ChatPage: React.FC = () => {
  const { colors } = useTheme();

  // 상태
  const [sessions, setSessions] = useState<ChatSession[]>([]);
  const [currentRoomId, setCurrentRoomId] = useState<number | null>(null);
  const [messages, setMessages] = useState<ChatMessageType[]>([]);
  const [inputMessage, setInputMessage] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [isSending, setIsSending] = useState(false);

  const messagesEndRef = useRef<HTMLDivElement>(null);
  const skipLoadHistoryRef = useRef(false); // 새 채팅방 생성 시 히스토리 로드 스킵용

  // ============================================
  // 채팅방 목록 로드
  // ============================================
  const loadChatRooms = useCallback(async () => {
    try {
      setIsLoading(true);
      const rooms = await getChatRooms();
      const convertedSessions = rooms.map(convertRoomToSession);
      setSessions(convertedSessions);

      // 첫 번째 방 선택
      if (rooms.length > 0) {
        setCurrentRoomId(rooms[0].id);
      }
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
    loadChatRooms();
  }, [loadChatRooms]);

  // ============================================
  // 방 선택 시 기록 로드
  // ============================================
  useEffect(() => {
    if (currentRoomId !== null) {
      // 새 채팅방 생성 직후에는 히스토리 로드 스킵
      if (skipLoadHistoryRef.current) {
        console.log('[ChatPage] 새 채팅방이므로 히스토리 로드 스킵');
        skipLoadHistoryRef.current = false;
        return;
      }
      console.log('[ChatPage] 채팅 기록 로드:', currentRoomId);
      loadChatHistory(currentRoomId);
    } else {
      console.log('[ChatPage] 새 채팅 - 메시지 초기화');
      setMessages([]);
    }
  }, [currentRoomId, loadChatHistory]);

  // ============================================
  // 스크롤
  // ============================================
  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages]);

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
  // 메시지 전송
  // ============================================
  const handleSendMessage = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!inputMessage.trim() || isSending) return;

    const question = inputMessage.trim();
    setInputMessage('');
    setIsSending(true);

    console.log('[ChatPage] 메시지 전송 시작, currentRoomId:', currentRoomId);

    // 사용자 메시지 즉시 표시
    const userMessage: ChatMessageType = {
      id: `temp-user-${Date.now()}`,
      role: 'user',
      content: question,
      timestamp: new Date(),
    };
    setMessages((prev) => {
      console.log('[ChatPage] 사용자 메시지 추가, 이전 메시지 수:', prev.length);
      return [...prev, userMessage];
    });

    try {
      // API 호출
      const response = await sendChat({
        chatRoomId: currentRoomId,
        question,
      });

      console.log('[ChatPage] API 응답 받음, chatRoomId:', response.chatRoomId);

      const isNewRoom = currentRoomId === null;
      
      // AI 응답 즉시 표시 (roomId 변경 전에 먼저 추가)
      const aiMessage: ChatMessageType = {
        id: `temp-ai-${Date.now()}`,
        role: 'assistant',
        content: response.answer,
        timestamp: new Date(),
      };
      setMessages((prev) => {
        console.log('[ChatPage] AI 응답 추가, 이전 메시지 수:', prev.length);
        return [...prev, aiMessage];
      });

      // 새 채팅방이면 세션 목록에 추가하고 현재 방 ID 설정
      if (isNewRoom) {
        console.log('[ChatPage] 새 채팅방 생성');
        const newSession: ChatSession = {
          id: String(response.chatRoomId),
          title: question.slice(0, 30),
          messages: [],
          createdAt: new Date(),
        };
        setSessions((prev) => [newSession, ...prev]);
        
        // 새 채팅방이므로 useEffect에서 히스토리 로드 스킵
        skipLoadHistoryRef.current = true;
        console.log('[ChatPage] skipLoadHistoryRef 설정 완료, roomId 변경:', response.chatRoomId);
        setCurrentRoomId(response.chatRoomId);
      } else {
        console.log('[ChatPage] 기존 채팅방에 메시지 추가');
        // 기존 채팅방: 백엔드와 동기화를 위해 채팅 기록 다시 로드
        setTimeout(() => {
          loadChatHistory(currentRoomId!);
        }, 300);
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
    }
  };

  // ============================================
  // 현재 세션 ID (사이드바용)
  // ============================================
  const currentSessionId = currentRoomId !== null ? String(currentRoomId) : '';

  return (
    <div className={styles.container}>
      <ChatSidebar
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
                원하는 도면, 말로 찾으세요
              </h2>
              <p className={styles.emptySubtitle} style={{ color: colors.textSecondary }}>
                "방 3개, 화장실 2개" 입력하면 즉시 추천
              </p>
            </div>
          ) : (
            <div>
              {messages.map((message) => (
                <ChatMessage key={message.id} message={message} />
              ))}
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
          <form onSubmit={handleSendMessage} className={styles.inputForm}>
            <input
              type="text"
              placeholder="메시지를 입력하세요..."
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
              disabled={isSending}
              className={styles.sendButton}
              style={{
                backgroundColor: isSending ? colors.textSecondary : colors.primary
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
