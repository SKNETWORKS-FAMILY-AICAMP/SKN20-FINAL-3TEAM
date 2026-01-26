// ============================================
// App - Main Application Entry Point
// ============================================

import { BrowserRouter as Router, Routes, Route, Navigate } from 'react-router-dom';
import { ThemeProvider } from '@/shared/contexts';

// Feature Pages
import { AuthPage } from '@/features/auth';
import { ChatPage } from '@/features/chat';
import { ProfilePage } from '@/features/profile';
import { FileUploadPage } from '@/features/floor-plan';
import { DashboardPage, UsersPage, FloorPlansPage, LogsPage, SettingsPage } from '@/features/admin';

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
