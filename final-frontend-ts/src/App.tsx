// ============================================
// App - Main Application Entry Point
// ============================================

import { BrowserRouter as Router, Routes, Route, Navigate } from 'react-router-dom';
import { Toaster } from 'react-hot-toast';
import { ThemeProvider } from '@/shared/contexts/ThemeContext';
import { AuthProvider } from '@/shared/contexts/AuthContext';
import ProtectedRoute from '@/shared/components/ProtectedRoute/ProtectedRoute';

// Feature Pages
import AuthPage from '@/features/auth/AuthPage';
import ChatPage from '@/features/chat/ChatPage';
import ProfilePage from '@/features/profile/ProfilePage';
import FileUploadPage from '@/features/floor-plan/FileUploadPage';
import { DashboardPage } from '@/features/admin/pages/DashboardPage';
import { FloorPlansPage } from '@/features/admin/pages/FloorPlansPage';
import { LogsPage } from '@/features/admin/pages/LogsPage';

function App() {
  return (
    <AuthProvider>
      <ThemeProvider>
        <Toaster />
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

            {/* Main app pages - Protected */}
            <Route path="/main" element={<ProtectedRoute><ChatPage /></ProtectedRoute>} />
            <Route path="/profile" element={<ProtectedRoute><ProfilePage /></ProtectedRoute>} />
            <Route path="/file-upload" element={<ProtectedRoute><FileUploadPage /></ProtectedRoute>} />

            {/* Admin pages - Protected */}
            <Route path="/admin" element={<ProtectedRoute><DashboardPage /></ProtectedRoute>} />
            <Route path="/admin/floor-plans" element={<ProtectedRoute><FloorPlansPage /></ProtectedRoute>} />
            <Route path="/admin/logs" element={<ProtectedRoute><LogsPage /></ProtectedRoute>} />
          </Routes>
        </Router>
      </ThemeProvider>
    </AuthProvider>
  );
}

export default App;
