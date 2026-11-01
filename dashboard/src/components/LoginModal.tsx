import React, { useState } from "react";
import { useAuth, SEEDED_DEMO_ACCOUNTS } from "../auth/AuthContext";

export const LoginModal: React.FC = () => {
  const { isLoginModalOpen, closeLoginModal, login, loginAsDemoAccount, user, isDemoMode } = useAuth();
  const [username, setUsername] = useState<string>("");
  const [password, setPassword] = useState<string>("");
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState<boolean>(false);

  if (!isLoginModalOpen) return null;

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!username.trim() || !password.trim()) {
      setErrorMessage("Username and password are required.");
      return;
    }

    setIsSubmitting(true);
    setErrorMessage(null);

    const res = await login(username.trim(), password);
    setIsSubmitting(false);

    if (!res.success) {
      setErrorMessage(res.error || "Authentication failed.");
    }
  };

  const handleDemoSelect = async (demoUsername: string) => {
    setIsSubmitting(true);
    setErrorMessage(null);
    const success = await loginAsDemoAccount(demoUsername);
    setIsSubmitting(false);
    if (!success) {
      setErrorMessage("Could not authenticate with demo account.");
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm p-4">
      <div className="w-full max-w-lg bg-[#FFFFFF] dark:bg-[#161618] border border-[#E5E5E3] dark:border-[#2A2A2D] shadow-2xl p-6 space-y-6">
        {/* Header */}
        <div className="flex items-center justify-between border-b border-[#E5E5E3] dark:border-[#2A2A2D] pb-4">
          <div>
            <h2 className="text-sm font-semibold tracking-wider uppercase text-[#111111] dark:text-[#EDEDEA]">
              Authentication & Role Access Gate
            </h2>
            <p className="text-xs text-[#6B6B66] mt-0.5">
              Backend token validation and server-side RBAC enforcement
            </p>
          </div>
          {user && (
            <button
              onClick={closeLoginModal}
              className="text-xs text-[#6B6B66] hover:text-[#111111] dark:hover:text-[#EDEDEA] uppercase tracking-wider"
            >
              Close
            </button>
          )}
        </div>

        {/* Error Alert */}
        {errorMessage && (
          <div className="border border-red-500/30 bg-red-500/10 p-3 text-xs text-red-600 dark:text-red-400">
            <span className="font-semibold uppercase tracking-wider block mb-0.5">Authentication Error</span>
            {errorMessage}
          </div>
        )}

        {/* Credentials Form */}
        <form onSubmit={handleSubmit} className="space-y-4">
          <div>
            <label className="block text-xs uppercase tracking-wider font-medium text-[#6B6B66] mb-1">
              Username
            </label>
            <input
              type="text"
              value={username}
              onChange={(e) => setUsername(e.target.value)}
              placeholder="e.g. engineer, admin, auditor"
              className="w-full bg-[#FAFAF9] dark:bg-[#0F0F10] border border-[#E5E5E3] dark:border-[#2A2A2D] px-3 py-2 text-xs text-[#111111] dark:text-[#EDEDEA] focus:outline-none focus:border-[#111111] dark:focus:border-[#EDEDEA]"
            />
          </div>

          <div>
            <label className="block text-xs uppercase tracking-wider font-medium text-[#6B6B66] mb-1">
              Password
            </label>
            <input
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              placeholder="Enter account password"
              className="w-full bg-[#FAFAF9] dark:bg-[#0F0F10] border border-[#E5E5E3] dark:border-[#2A2A2D] px-3 py-2 text-xs text-[#111111] dark:text-[#EDEDEA] focus:outline-none focus:border-[#111111] dark:focus:border-[#EDEDEA]"
            />
          </div>

          <button
            type="submit"
            disabled={isSubmitting}
            className="w-full py-2.5 bg-[#111111] dark:bg-[#EDEDEA] text-[#FAFAF9] dark:text-[#0F0F10] text-xs font-medium uppercase tracking-wider hover:opacity-90 transition-opacity disabled:opacity-50"
          >
            {isSubmitting ? "Authenticating..." : "Sign In with Credentials"}
          </button>
        </form>

        {/* Quick Select Demo Accounts (Gated behind DEMO_MODE) */}
        {isDemoMode ? (
          <div className="border-t border-[#E5E5E3] dark:border-[#2A2A2D] pt-4 space-y-3">
            <div className="flex items-center justify-between">
              <span className="text-xs uppercase tracking-wider font-medium text-[#6B6B66]">
                Demo Sandbox Access (1-Click Switch)
              </span>
              <span className="text-[10px] text-[#6B6B66] uppercase">8 Roles Active</span>
            </div>

            <div className="grid grid-cols-2 gap-2">
              {SEEDED_DEMO_ACCOUNTS.map((acc) => {
                const isCurrent = user?.username === acc.username;
                return (
                  <button
                    key={acc.username}
                    type="button"
                    onClick={() => handleDemoSelect(acc.username)}
                    disabled={isSubmitting}
                    className={`text-left p-2.5 border transition-all text-xs ${
                      isCurrent
                        ? "border-[#111111] dark:border-[#EDEDEA] bg-[#111111]/5 dark:bg-[#EDEDEA]/10 font-semibold"
                        : "border-[#E5E5E3] dark:border-[#2A2A2D] hover:border-[#6B6B66] bg-[#FAFAF9] dark:bg-[#0F0F10]"
                    }`}
                  >
                    <div className="flex items-center justify-between">
                      <span className="text-[#111111] dark:text-[#EDEDEA]">{acc.title}</span>
                      {isCurrent && (
                        <span className="text-[9px] uppercase tracking-wider text-[#6B6B66]">Active</span>
                      )}
                    </div>
                    <div className="text-[10px] text-[#6B6B66] mt-0.5">
                      User: {acc.username} ({acc.department})
                    </div>
                  </button>
                );
              })}
            </div>
          </div>
        ) : (
          <div className="border-t border-[#E5E5E3] dark:border-[#2A2A2D] pt-3 text-[11px] text-[#6B6B66]">
            Production Authentication: Demo shortcuts disabled. Enter registered operator credentials.
          </div>
        )}

        {/* Security Invariant Note */}
        <div className="text-[11px] text-[#6B6B66] border-t border-[#E5E5E3] dark:border-[#2A2A2D] pt-3">
          Identity is derived strictly from server-validated JWT tokens. All requests transmit Bearer authentication headers.
        </div>
      </div>
    </div>
  );
};
