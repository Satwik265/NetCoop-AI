import React, { createContext, useContext, useState, useEffect } from "react";
import { UserRole } from "../rbac/roles";

export interface AuthUser {
  user_id: string;
  username: string;
  role: UserRole;
  full_name?: string;
  permissions: string[];
}

export interface DemoAccount {
  username: string;
  role: UserRole;
  title: string;
  department: string;
}

export const SEEDED_DEMO_ACCOUNTS: DemoAccount[] = [
  {
    username: "engineer",
    role: "network_engineer",
    title: "Network Engineer",
    department: "Infrastructure Engineering",
  },
  {
    username: "noc",
    role: "noc_operator",
    title: "NOC Operator",
    department: "Network Operations",
  },
  {
    username: "admin",
    role: "network_admin",
    title: "Network Admin",
    department: "Campus Systems",
  },
  {
    username: "security",
    role: "security_analyst",
    title: "Security Analyst",
    department: "SecOps Defense",
  },
  {
    username: "it_manager",
    role: "it_manager",
    title: "IT Manager",
    department: "IT Leadership",
  },
  {
    username: "platform_admin",
    role: "platform_admin",
    title: "Platform Admin",
    department: "Platform & SRE",
  },
  {
    username: "auditor",
    role: "auditor",
    title: "Compliance Auditor",
    department: "Governance & Risk",
  },
  {
    username: "helpdesk",
    role: "helpdesk",
    title: "Helpdesk Operator",
    department: "Campus Helpdesk",
  },
];

interface AuthContextType {
  user: AuthUser | null;
  token: string | null;
  isDemoMode: boolean;
  login: (username: string, password: string) => Promise<{ success: boolean; error?: string }>;
  loginAsDemoAccount: (username: string) => Promise<boolean>;
  logout: () => void;
  isLoginModalOpen: boolean;
  openLoginModal: () => void;
  closeLoginModal: () => void;
  authFetch: (url: string, init?: RequestInit) => Promise<Response>;
  lastForbiddenError: string | null;
  clearForbiddenError: () => void;
}

const AuthContext = createContext<AuthContextType | undefined>(undefined);

export const AuthProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const [token, setToken] = useState<string | null>(() => {
    return sessionStorage.getItem("netcoop_token");
  });

  const [user, setUser] = useState<AuthUser | null>(() => {
    const saved = sessionStorage.getItem("netcoop_user");
    if (saved) {
      try {
        return JSON.parse(saved);
      } catch {
        return null;
      }
    }
    return null;
  });

  const [isDemoMode, setIsDemoMode] = useState<boolean>(true);
  const [isLoginModalOpen, setIsLoginModalOpen] = useState<boolean>(false);
  const [lastForbiddenError, setLastForbiddenError] = useState<string | null>(null);

  const clearForbiddenError = () => setLastForbiddenError(null);

  // Discover server runtime mode and demo availability
  useEffect(() => {
    fetch("/api/features")
      .then((res) => res.json())
      .then((data) => {
        if (typeof data.DEMO_MODE_ENABLED === "boolean") {
          setIsDemoMode(data.DEMO_MODE_ENABLED);
        }
      })
      .catch(() => {
        setIsDemoMode(false);
      });
  }, []);

  const handleAuthSuccess = (accessToken: string, userData: any) => {
    const authUser: AuthUser = {
      user_id: userData.user_id || `user-${userData.username}`,
      username: userData.username,
      role: userData.role as UserRole,
      full_name: userData.full_name,
      permissions: userData.permissions || [],
    };
    setToken(accessToken);
    setUser(authUser);
    sessionStorage.setItem("netcoop_token", accessToken);
    sessionStorage.setItem("netcoop_user", JSON.stringify(authUser));
    localStorage.setItem("netcoop_user_role", authUser.role);
    setIsLoginModalOpen(false);
    setLastForbiddenError(null);
  };

  const login = async (username: string, password: string): Promise<{ success: boolean; error?: string }> => {
    try {
      const res = await fetch("/api/auth/login", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ username, password }),
      });

      if (!res.ok) {
        const errData = await res.json().catch(() => ({}));
        return {
          success: false,
          error: errData.detail || "Authentication failed. Check credentials.",
        };
      }

      const data = await res.json();
      handleAuthSuccess(data.access_token, data);
      return { success: true };
    } catch (err: any) {
      return { success: false, error: err.message || "Network error connecting to auth server." };
    }
  };

  const loginAsDemoAccount = async (username: string): Promise<boolean> => {
    try {
      const res = await fetch("/api/auth/demo-login", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ username }),
      });
      if (!res.ok) {
        return false;
      }
      const data = await res.json();
      handleAuthSuccess(data.access_token, data);
      return true;
    } catch {
      return false;
    }
  };

  const logout = () => {
    if (token) {
      fetch("/api/auth/logout", {
        method: "POST",
        headers: { Authorization: `Bearer ${token}` },
      }).catch(() => {});
    }
    setToken(null);
    setUser(null);
    sessionStorage.removeItem("netcoop_token");
    sessionStorage.removeItem("netcoop_user");
    setIsLoginModalOpen(true);
  };

  const authFetch = async (url: string, init: RequestInit = {}): Promise<Response> => {
    const headers = new Headers(init.headers || {});
    const activeToken = token || sessionStorage.getItem("netcoop_token");
    if (activeToken && !headers.has("Authorization")) {
      headers.set("Authorization", `Bearer ${activeToken}`);
    }

    const res = await fetch(url, { ...init, headers });

    if (res.status === 401) {
      setToken(null);
      setUser(null);
      sessionStorage.removeItem("netcoop_token");
      sessionStorage.removeItem("netcoop_user");
      setIsLoginModalOpen(true);
    } else if (res.status === 403) {
      try {
        const errJson = await res.clone().json();
        setLastForbiddenError(errJson.detail || "Operation forbidden by server-side RBAC policy.");
      } catch {
        setLastForbiddenError("Forbidden: Insufficient permissions for this action.");
      }
    }

    return res;
  };

  // Require active credential entry on startup if unauthenticated (no auto-login)
  useEffect(() => {
    if (!token && !sessionStorage.getItem("netcoop_token")) {
      setIsLoginModalOpen(true);
    }
  }, []);

  return (
    <AuthContext.Provider
      value={{
        user,
        token,
        isDemoMode,
        login,
        loginAsDemoAccount,
        logout,
        isLoginModalOpen,
        openLoginModal: () => setIsLoginModalOpen(true),
        closeLoginModal: () => setIsLoginModalOpen(false),
        authFetch,
        lastForbiddenError,
        clearForbiddenError,
      }}
    >
      {children}
    </AuthContext.Provider>
  );
};

export const apiFetch = async (url: string, init: RequestInit = {}): Promise<Response> => {
  const headers = new Headers(init.headers || {});
  const activeToken = sessionStorage.getItem("netcoop_token");
  if (activeToken && !headers.has("Authorization")) {
    headers.set("Authorization", `Bearer ${activeToken}`);
  }
  const res = await fetch(url, { ...init, headers });
  if (res.status === 401) {
    sessionStorage.removeItem("netcoop_token");
    sessionStorage.removeItem("netcoop_user");
    window.dispatchEvent(new CustomEvent("netcoop_unauthorized"));
  }
  return res;
};

export const useAuth = (): AuthContextType => {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error("useAuth must be used within an AuthProvider");
  }
  return context;
};
