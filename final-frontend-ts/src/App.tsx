// ============================================
// App - Main Application Entry Point
// ============================================

import { BrowserRouter as Router, Routes, Route, Navigate } from 'react-router-dom';
import { ThemeProvider } from '@/shared/contexts/ThemeContext';

// Feature Pages
import AuthPage from '@/features/auth/AuthPage';
import ChatPage from '@/features/chat/ChatPage';
import ProfilePage from '@/features/profile/ProfilePage';
import FileUploadPage from '@/features/floor-plan/FileUploadPage';
import { DashboardPage } from '@/features/admin/pages/DashboardPage';
import { UsersPage } from '@/features/admin/pages/UsersPage';
import { FloorPlansPage } from '@/features/admin/pages/FloorPlansPage';
import { LogsPage } from '@/features/admin/pages/LogsPage';
import { SettingsPage } from '@/features/admin/pages/SettingsPage';

function App() {
  return (
    <ThemeProvider>
      <Router>
        <Routes>
          {/* Default route redirects to auth */}
          <Route path="/" element={<Navigate to="/auth" replace />} />

          {/* Unified authentication page */}
          <Route path="/auth" element={<AuthPage />} />

          {/* Legacy routes redirect to auth */}
          <Route path="/login" element={<Navigate to="/auth" replace />} />
          <Route path="/signup" element={<Navigate to="/auth" replace />} />
          <Route path="/forgot-password" element={<Navigate to="/auth" replace />} />
          <Route path="/reset-password" element={<Navigate to="/auth" replace />} />
          <Route path="/password-reset-success" element={<Navigate to="/auth" replace />} />

          {/* Main app pages */}
          <Route path="/main" element={<ChatPage />} />
          <Route path="/profile" element={<ProfilePage />} />
          <Route path="/file-upload" element={<FileUploadPage />} />

          {/* Admin pages */}
          <Route path="/admin" element={<DashboardPage />} />
          <Route path="/admin/users" element={<UsersPage />} />
          <Route path="/admin/floor-plans" element={<FloorPlansPage />} />
          <Route path="/admin/logs" element={<LogsPage />} />
          <Route path="/admin/settings" element={<SettingsPage />} />
        </Routes>
      </Router>
    </ThemeProvider>
  );
}

export default App;
