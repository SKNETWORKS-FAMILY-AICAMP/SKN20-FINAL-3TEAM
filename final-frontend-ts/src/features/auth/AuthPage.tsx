import React, { useState } from 'react';
import AuthLayout from './AuthLayout';
import Login from './login/Login';
import Signup from './signup/Signup';
import PasswordReset from './password-reset/PasswordReset';
import type { AuthView } from './types/auth.types';

const AuthPage: React.FC = () => {
  const [currentView, setCurrentView] = useState<AuthView>('login');

  const handleViewChange = (view: AuthView) => {
    setCurrentView(view);
  };

  const renderForm = () => {
    switch (currentView) {
      case 'login':
        return <Login onViewChange={handleViewChange} />;
      case 'signup':
        return <Signup onViewChange={handleViewChange} />;
      case 'forgot-password':
      case 'reset-password':
        return <PasswordReset onViewChange={handleViewChange} />;
      default:
        return <Login onViewChange={handleViewChange} />;
    }
  };

  return (
    <AuthLayout>
      {renderForm()}
    </AuthLayout>
  );
};

export default AuthPage;
