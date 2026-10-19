import React, { createContext, useContext, useState, useEffect } from 'react';
import { User } from '../types';
import { api } from '../services/api';

interface AuthContextType {
  user: User | null;
  isAuthenticated: boolean;
  signIn: (email: string) => Promise<void>;
  signUp: (email: string) => Promise<void>;
  signOut: () => void;
  switchUser: (newUserId: string) => void;
}

const AuthContext = createContext<AuthContextType | undefined>(undefined);

export const AuthProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const [user, setUser] = useState<User | null>(() => {
    const saved = localStorage.getItem('orion_user');
    if (saved) {
      try {
        return JSON.parse(saved);
      } catch {
        return null;
      }
    }
    // Default active researcher session
    return {
      id: 'user_dev_researcher_001',
      email: 'researcher@orion-assistant.ai',
      role: 'authenticated',
    };
  });

  useEffect(() => {
    if (user) {
      localStorage.setItem('orion_user', JSON.stringify(user));
      api.setAuth(null, user.id);
    } else {
      localStorage.removeItem('orion_user');
    }
  }, [user]);

  const signIn = async (email: string) => {
    const id = `user_${email.split('@')[0].replace(/[^a-zA-Z0-9]/g, '_')}`;
    const newUser: User = { id, email, role: 'authenticated' };
    setUser(newUser);
  };

  const signUp = async (email: string) => {
    await signIn(email);
  };

  const signOut = () => {
    setUser(null);
  };

  const switchUser = (newUserId: string) => {
    const newUser: User = {
      id: newUserId,
      email: `${newUserId}@orion.dev`,
      role: 'authenticated',
    };
    setUser(newUser);
  };

  return (
    <AuthContext.Provider
      value={{
        user,
        isAuthenticated: !!user,
        signIn,
        signUp,
        signOut,
        switchUser,
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
