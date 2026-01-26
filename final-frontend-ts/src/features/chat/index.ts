// Chat Feature - Public API

// Types
export type {
  ChatMessage,
  ChatSession,
  ChatSidebarProps,
  ChatMessageProps,
} from './types';

// API
export * from './api';

// Data
export { mockChatSessions } from './data';

// Components (rename to avoid conflict with type)
export { default as ChatMessageComponent } from './ChatMessage';
export { default as ChatSidebar } from './ChatSidebar';

// Page
export { default as ChatPage } from './ChatPage';
