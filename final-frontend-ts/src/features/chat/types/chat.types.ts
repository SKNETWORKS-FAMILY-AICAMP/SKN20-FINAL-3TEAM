// ============================================
// Chat Feature - Type Definitions
// ============================================

// ============================================
// API Request/Response Types
// ============================================

// 채팅방 (ChatRoom) - 백엔드 엔티티와 일치
export interface ChatRoom {
  id: number;
  name: string;
  createdAt: string;
}

// 채팅 기록 (ChatHistory)
export interface ChatHistory {
  id: number;
  question: string;
  answer: string;
  createdAt: string;
}

// 채팅 요청
export interface ChatRequest {
  chatRoomId: number | null;
  question: string;
}

// 채팅 응답
export interface ChatResponse {
  answer: string;
  chatRoomId: number;
}

// 채팅방 이름 수정 요청
export interface EditRoomNameRequest {
  chatRoomId: number;
  newName: string;
}

// 채팅방 삭제 요청
export interface DeleteRoomRequest {
  chatRoomId: number;
}

// 채팅 기록 조회 요청
export interface RoomHistoryRequest {
  chatRoomId: number;
}

// ============================================
// UI Component Types
// ============================================

// 채팅 메시지 타입 (UI용)
export interface ChatMessage {
  id: string;
  role: 'user' | 'assistant';
  content: string;
  timestamp: Date;
}

// 채팅 세션 타입 (UI용 - ChatRoom 기반)
export interface ChatSession {
  id: string;
  title: string;
  messages: ChatMessage[];
  createdAt: Date;
}

// 채팅 사이드바 Props
export interface ChatSidebarProps {
  sessions: ChatSession[];
  currentSessionId: string;
  onSessionClick: (sessionId: string) => void;
  onNewChat: () => void;
  onDeleteSession: (sessionId: string) => void;
  onRenameSession: (sessionId: string, newName: string) => void;
  onClearAll: () => void;
}

// 채팅 메시지 Props
export interface ChatMessageProps {
  message: ChatMessage;
}
