import React, { createContext, useContext, useState, useEffect, useCallback } from 'react';
import { User } from '../types';
import { api } from '../services/api';

interface SignUpOptions {
  email: string;
  password?: string;
  name?: string;
  institution?: string;
}

interface AuthContextType {
  user: User | null;
  isAuthenticated: boolean;
  isLoading: boolean;
  signIn: (email: string, password?: string) => Promise<void>;
  signUp: (dataOrEmail: string | SignUpOptions, password?: string, name?: string, institution?: string) => Promise<void>;
  signOut: () => Promise<void>;
  switchUser: (newUserId: string) => void;
  checkSession: () => Promise<void>;
}

const AuthContext = createContext<AuthContextType | undefined>(undefined);

export const AuthProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const [user, setUser] = useState<User | null>(null);
  const [isLoading, setIsLoading] = useState<boolean>(true);

  const checkSession = useCallback(async () => {
    try {
      const currentUser = await api.getMe();
      if (currentUser && currentUser.id) {
        setUser(currentUser);
        api.setAuth(null, currentUser.id);
      } else {
        setUser(null);
      }
    } catch {
      setUser(null);
    } finally {
      setIsLoading(false);
    }
  }, []);

  useEffect(() => {
    checkSession();
  }, [checkSession]);

  const signIn = async (email: string, password?: string) => {
    const res = await api.login({ email, password: password || '' });
    setUser(res.user);
    api.setAuth(res.access_token, res.user.id);
  };

  const signUp = async (
    dataOrEmail: string | SignUpOptions,
    password?: string,
    name?: string,
    institution?: string,
  ) => {
    let payload: { email: string; password?: string; display_name: string; institution?: string | null };
    if (typeof dataOrEmail === 'string') {
      payload = {
        email: dataOrEmail,
        password,
        display_name: name || dataOrEmail.split('@')[0],
        institution: institution || null,
      };
    } else {
      payload = {
        email: dataOrEmail.email,
        password: dataOrEmail.password,
        display_name: dataOrEmail.name || dataOrEmail.email.split('@')[0],
        institution: dataOrEmail.institution || null,
      };
    }

    const res = await api.register(payload);
    setUser(res.user);
    api.setAuth(res.access_token, res.user.id);
  };

  const signOut = async () => {
    try {
      await api.logout();
    } catch {
      // Proceed with local sign out regardless of network error
    } finally {
      setUser(null);
      api.setAuth(null, '');
    }
  };

  const switchUser = useCallback((newUserId: string) => {
    // Only permit tenant switching in development mode
    if (!import.meta.env.DEV) {
      console.warn('Tenant switching is disabled in production.');
      return;
    }
    const newUser: User = {
      id: newUserId,
      email: `${newUserId}@orion.dev`,
      role: 'authenticated',
      display_name: newUserId,
    };
    setUser(newUser);
    api.setAuth(null, newUserId);
  }, []);

  // Expose switchUser for automated development test harnesses only
  useEffect(() => {
    if (import.meta.env.DEV && typeof window !== 'undefined') {
      (window as any).__ORION_DEV_SWITCH_USER__ = switchUser;
    }
    return () => {
      if (typeof window !== 'undefined') {
        delete (window as any).__ORION_DEV_SWITCH_USER__;
      }
    };
  }, [switchUser]);

  return (
    <AuthContext.Provider
      value={{
        user,
        isAuthenticated: !!user,
        isLoading,
        signIn,
        signUp,
        signOut,
        switchUser,
        checkSession,
      }}
    >
      {children}
    </AuthContext.Provider>
  );
};

export const useAuth = () => {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error('useAuth must be used within an AuthProvider');
  }
  return context;
};
