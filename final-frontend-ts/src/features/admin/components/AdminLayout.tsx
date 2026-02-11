// ============================================
// AdminLayout - Admin Dashboard Layout with Sidebar
// ============================================

import type { ReactNode } from 'react';
import { NavLink, useNavigate } from 'react-router-dom';
import {
  FiGrid,
  FiFolder,
  FiFileText,
  FiLogOut,
  FiArrowLeft,
  FiShield
} from 'react-icons/fi';
import { useTheme } from '@/shared/contexts/ThemeContext';
import styles from './AdminLayout.module.css';

interface AdminLayoutProps {
  children: ReactNode;
}

// 사이드바 메뉴 아이템
const menuItems = [
  { path: '/admin', icon: FiGrid, label: '대시보드', exact: true },
  { path: '/admin/floor-plans', icon: FiFolder, label: '도면 DB' },
  { path: '/admin/logs', icon: FiFileText, label: '활동 로그' },
];

export function AdminLayout({ children }: AdminLayoutProps) {
  const { theme } = useTheme();
  const navigate = useNavigate();

  const handleLogout = () => {
    // TODO: 로그아웃 처리
    navigate('/auth');
  };

  const handleBackToMain = () => {
    navigate('/main');
  };

  return (
    <div className={`${styles.container} ${styles[theme]}`}>
      {/* 사이드바 */}
      <aside className={styles.sidebar}>
        {/* 로고/타이틀 */}
        <div className={styles.sidebarHeader}>
          <FiShield className={styles.logo} />
          <span className={styles.title}>Admin</span>
        </div>

        {/* 네비게이션 메뉴 */}
        <nav className={styles.nav}>
          {menuItems.map((item) => (
            <NavLink
              key={item.path}
              to={item.path}
              end={item.exact}
              className={({ isActive }) =>
                `${styles.navItem} ${isActive ? styles.active : ''}`
              }
            >
              <item.icon className={styles.navIcon} />
              <span className={styles.navLabel}>{item.label}</span>
            </NavLink>
          ))}
        </nav>

        {/* 하단 버튼들 */}
        <div className={styles.sidebarFooter}>
          <button className={styles.footerBtn} onClick={handleBackToMain}>
            <FiArrowLeft /> 메인으로
          </button>
          <button className={styles.footerBtn} onClick={handleLogout}>
            <FiLogOut /> 로그아웃
          </button>
        </div>
      </aside>

      {/* 메인 영역 */}
      <div className={styles.main}>
        {/* 헤더 */}
        <header className={styles.header}>
          <h1 className={styles.pageTitle}>Admin Dashboard</h1>
          <div className={styles.headerRight}>
            <span className={styles.adminBadge}>관리자</span>
          </div>
        </header>

        {/* 컨텐츠 */}
        <main className={styles.content}>
          {children}
        </main>
      </div>
    </div>
  );
}
