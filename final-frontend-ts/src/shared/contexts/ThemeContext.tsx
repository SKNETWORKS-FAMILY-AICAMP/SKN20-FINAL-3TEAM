import React, { createContext, useContext, useEffect } from 'react';
import type { ReactNode } from 'react';
import { lightColors } from '@/shared/styles/colors';
import type { ThemeColors } from '@/shared/styles/colors';

interface ThemeContextType {
  theme: 'light';
  colors: ThemeColors;
  toggleTheme: () => void;
  setTheme: () => void;
}

const ThemeContext = createContext<ThemeContextType | undefined>(undefined);

interface ThemeProviderProps {
  children: ReactNode;
}

export const ThemeProvider: React.FC<ThemeProviderProps> = ({ children }) => {
  const theme = 'light' as const;
  const colors = lightColors;

  useEffect(() => {
    document.documentElement.setAttribute('data-theme', 'light');
    document.body.style.backgroundColor = colors.background;
    document.body.style.color = colors.textPrimary;
  }, [colors]);

  // 더 이상 토글 안 함 (빈 함수)
  const toggleTheme = () => {};
  const setTheme = () => {};

  return (
    <ThemeContext.Provider value={{ theme, colors, toggleTheme, setTheme }}>
      {children}
    </ThemeContext.Provider>
  );
};

export const useTheme = (): ThemeContextType => {
  const context = useContext(ThemeContext);
  if (!context) {
    throw new Error('useTheme must be used within a ThemeProvider');
  }
  return context;
};

export default ThemeContext;
