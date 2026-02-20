import React, { useState } from 'react';
import { useNavigate, useLocation } from 'react-router-dom';
import { BiChat } from 'react-icons/bi';
import { FiEdit, FiTrash2, FiChevronLeft, FiChevronRight, FiUser } from 'react-icons/fi';
import { useTheme } from '@/shared/contexts/ThemeContext';
import type { ChatSession } from '@/features/chat/types/chat.types';
import styles from './AppSidebar.module.css';

interface AppSidebarProps {
  // Chat-specific props (optional - only needed on chat page)
  sessions?: ChatSession[];
  currentSessionId?: string;
  onSessionClick?: (sessionId: string) => void;
  onNewChat?: () => void;
  onDeleteSession?: (sessionId: string) => void;
  onClearAll?: () => void;
}

const AppSidebar: React.FC<AppSidebarProps> = ({
  sessions = [],
  currentSessionId = '',
  onSessionClick,
  onNewChat,
  onDeleteSession,
  onClearAll,
}) => {
  const { colors } = useTheme();
  const navigate = useNavigate();
  const location = useLocation();
  const [collapsed, setCollapsed] = useState(false);
  const [hoveredSession, setHoveredSession] = useState<string | null>(null);

  const isChat = location.pathname === '/main';
  const isFloorPlan = location.pathname === '/file-upload';

  return (
    <div
      className={`${styles.sidebar} ${collapsed ? styles.collapsed : ''}`}
      style={{
        backgroundColor: colors.sidebarBg,
        borderRight: `1px solid ${colors.border}`,
      }}
    >
      {/* Header - Logo */}
      <div className={styles.header}>
        {!collapsed && (
          <h2
            className={styles.brand}
            style={{ color: colors.textPrimary }}
          >
            ARAE
          </h2>
        )}
        <button
          className={styles.toggleBtn}
          onClick={() => setCollapsed(!collapsed)}
          style={{ color: colors.textSecondary }}
          title={collapsed ? '사이드바 열기' : '사이드바 접기'}
        >
          {collapsed ? <FiChevronRight size={18} /> : <FiChevronLeft size={18} />}
        </button>
      </div>

      {/* Navigation */}
      <nav className={styles.nav}>
        <div
          className={`${styles.navItem} ${isChat ? styles.navItemActive : ''}`}
          onClick={() => navigate('/main')}
          title="채팅"
          style={
            isChat
              ? { backgroundColor: '#FEF3C7', borderLeft: `3px solid ${colors.primary}` }
              : {}
          }
        >
          <BiChat size={20} />
          {!collapsed && <span className={styles.navLabel}>채팅</span>}
        </div>
        <div
          className={`${styles.navItem} ${isFloorPlan ? styles.navItemActive : ''}`}
          onClick={() => navigate('/file-upload')}
          title="도면 등록"
          style={
            isFloorPlan
              ? { backgroundColor: '#FEF3C7', borderLeft: `3px solid ${colors.primary}` }
              : {}
          }
        >
          <FiEdit size={20} />
          {!collapsed && <span className={styles.navLabel}>도면 등록</span>}
        </div>
      </nav>

      {/* Chat section - only on chat page and expanded */}
      {isChat && !collapsed && (
        <>
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
                onClick={() => onSessionClick?.(session.id)}
                onMouseEnter={() => setHoveredSession(session.id)}
                onMouseLeave={() => setHoveredSession(null)}
                className={styles.sessionItem}
                style={{
                  backgroundColor:
                    currentSessionId === session.id ? colors.inputBg : 'transparent',
                }}
              >
                <div className={styles.sessionContent}>
                  <span className={styles.sessionIcon}>
                    <BiChat size={16} />
                  </span>
                  <span
                    className={styles.sessionTitle}
                    style={{ color: colors.textPrimary }}
                  >
                    {session.title}
                  </span>
                </div>
                {hoveredSession === session.id && (
                  <button
                    onClick={(e) => {
                      e.stopPropagation();
                      onDeleteSession?.(session.id);
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
        </>
      )}

      {/* Spacer */}
      <div className={styles.spacer} />

      {/* Bottom - Profile */}
      <div className={styles.bottomSection}>
        <div
          className={styles.navItem}
          onClick={() => navigate('/profile')}
          title="내 계정"
        >
          <FiUser size={20} />
          {!collapsed && <span className={styles.navLabel}>내 계정</span>}
        </div>
      </div>
    </div>
  );
};

export default AppSidebar;
