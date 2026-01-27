import React, { useState } from 'react';
import { BiChat } from 'react-icons/bi';
import { FiTrash2 } from 'react-icons/fi';
import { useTheme } from '@/shared/contexts/ThemeContext';
import type { ChatSidebarProps } from './types/chat.types';
import styles from './ChatSidebar.module.css';

const ChatSidebar: React.FC<ChatSidebarProps> = ({
  sessions,
  currentSessionId,
  onSessionClick,
  onNewChat,
  onDeleteSession,
  onRenameSession,
  onClearAll,
}) => {
  // onRenameSession은 추후 이름 수정 UI 추가 시 사용
  void onRenameSession;
  const { colors } = useTheme();
  const [hoveredSession, setHoveredSession] = useState<string | null>(null);

  return (
    <div
      className={styles.sidebar}
      style={{
        backgroundColor: colors.sidebarBg,
        borderRight: `1px solid ${colors.border}`,
      }}
    >
      <div className={styles.header}>
        <h2 className={styles.brand} style={{ color: colors.textPrimary, fontFamily: '"Special Gothic Expanded One", sans-serif' }}>
          ARAE
        </h2>
      </div>

      <button
        onClick={onNewChat}
        className={styles.newChatBtn}
        style={{ backgroundColor: colors.primary }}
      >
        + 새 검색
      </button>

      <div className={styles.listHeader}>
        <span className={styles.listLabel} style={{ color: colors.textSecondary }}>
          내 채팅
        </span>
        <button
          onClick={onClearAll}
          className={styles.clearBtn}
          style={{ color: colors.textSecondary }}
        >
          모두 지우기
        </button>
      </div>

      <div className={styles.sessionList}>
        {sessions.map((session) => (
          <div
            key={session.id}
            onClick={() => onSessionClick(session.id)}
            onMouseEnter={() => setHoveredSession(session.id)}
            onMouseLeave={() => setHoveredSession(null)}
            className={styles.sessionItem}
            style={{
              backgroundColor: currentSessionId === session.id ? colors.inputBg : 'transparent',
            }}
          >
            <div className={styles.sessionContent}>
              <span className={styles.sessionIcon}><BiChat size={16} /></span>
              <span className={styles.sessionTitle} style={{ color: colors.textPrimary }}>
                {session.title}
              </span>
            </div>
            {hoveredSession === session.id && (
              <button
                onClick={(e) => {
                  e.stopPropagation();
                  onDeleteSession(session.id);
                }}
                className={styles.deleteBtn}
                style={{ color: colors.textSecondary }}
              >
                <FiTrash2 size={14} />
              </button>
            )}
          </div>
        ))}
      </div>

      <div className={styles.bottomButtons}>
        <button
          onClick={() => window.location.href = '/file-upload'}
          className={styles.navBtn}
          style={{
            backgroundColor: colors.inputBg,
            border: `1px solid ${colors.border}`,
            color: colors.textPrimary,
          }}
        >
          내 도면 올리기
        </button>
        <button
          onClick={() => window.location.href = '/profile'}
          className={styles.navBtn}
          style={{
            backgroundColor: colors.inputBg,
            border: `1px solid ${colors.border}`,
            color: colors.textPrimary,
          }}
        >
          내 계정
        </button>
      </div>
    </div>
  );
};

export default ChatSidebar;
