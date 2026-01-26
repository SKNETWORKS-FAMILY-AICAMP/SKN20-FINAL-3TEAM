import React from 'react';
import { Logo } from '@/shared/components';
import { useTheme } from '@/shared/contexts';
import styles from './AuthLayout.module.css';

interface AuthLayoutProps {
  children: React.ReactNode;
}

const AuthLayout: React.FC<AuthLayoutProps> = ({ children }) => {
  const { colors } = useTheme();

  return (
    <div className={styles.container} style={{ backgroundColor: colors.background }}>
      <div
        className={styles.card}
        style={{
          backgroundColor: colors.white,
          boxShadow: '0 10px 40px rgba(0, 0, 0, 0.1)',
        }}
      >
        <div
          className={styles.leftPanel}
          style={{
            backgroundColor: colors.white,
            borderRight: `1px solid ${colors.border}`,
          }}
        >
          <Logo size={400} />
        </div>

        <div
          className={styles.rightPanel}
          style={{ backgroundColor: colors.white }}
        >
          {children}
        </div>
      </div>
    </div>
  );
};

export default AuthLayout;
