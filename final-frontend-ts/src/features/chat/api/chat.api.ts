// ============================================
// Chat Feature - API Functions
// ============================================

import { apiClient } from '@/shared/api';
import type {
  ChatRoom,
  ChatHistory,
  ChatRequest,
  ChatResponse,
  EditRoomNameRequest,
  DeleteRoomRequest,
  RoomHistoryRequest,
} from '../types';

const CHATBOT_BASE = '/api/chatbot';

// ============================================
// 1. 내 채팅방 목록 조회
// ============================================
export const getChatRooms = async (): Promise<ChatRoom[]> => {
  const response = await apiClient.post<ChatRoom[]>(`${CHATBOT_BASE}/sessionuser`);
  return response.data;
};

// ============================================
// 2. 채팅방별 채팅 기록 조회
// ============================================
export const getRoomHistory = async (
  params: RoomHistoryRequest
): Promise<ChatHistory[]> => {
  const response = await apiClient.post<ChatHistory[]>(
    `${CHATBOT_BASE}/roomhistory`,
    null,
    { params }
  );
  return response.data;
};

// ============================================
// 3. 질문 → 답변 (QnA) 및 저장
// ============================================
export const sendChat = async (params: ChatRequest): Promise<ChatResponse> => {
  const response = await apiClient.post<ChatResponse>(
    `${CHATBOT_BASE}/chat`,
    null,
    { params }
  );
  return response.data;
};

// ============================================
// 4. 채팅방 이름 수정
// ============================================
export const editRoomName = async (
  params: EditRoomNameRequest
): Promise<string> => {
  const response = await apiClient.post<string>(
    `${CHATBOT_BASE}/editroomname`,
    null,
    { params }
  );
  return response.data;
};

// ============================================
// 5. 채팅방 및 기록 삭제
// ============================================
export const deleteRoom = async (params: DeleteRoomRequest): Promise<string> => {
  const response = await apiClient.post<string>(
    `${CHATBOT_BASE}/deleteroom`,
    null,
    { params }
  );
  return response.data;
};

// ============================================
// 6. 내 모든 채팅방/기록 삭제
// ============================================
export const deleteAllRooms = async (): Promise<string> => {
  const response = await apiClient.post<string>(`${CHATBOT_BASE}/deleteallrooms`);
  return response.data;
};
