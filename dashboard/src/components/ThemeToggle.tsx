import React, { useEffect, useState } from "react";

export const ThemeToggle: React.FC = () => {
  const [isDark, setIsDark] = useState<boolean>(() => {
    const saved = localStorage.getItem("netcoop_theme");
    if (saved) return saved === "dark";
    return window.matchMedia("(prefers-color-scheme: dark)").matches;
  });

  useEffect(() => {
    if (isDark) {
      document.documentElement.classList.add("dark");
      localStorage.setItem("netcoop_theme", "dark");
    } else {
      document.documentElement.classList.remove("dark");
      localStorage.setItem("netcoop_theme", "light");
    }
  }, [isDark]);

  return (
    <button
      onClick={() => setIsDark((prev) => !prev)}
      className="px-3 py-1 bg-[#FAFAF9] dark:bg-[#0F0F10] border border-[#E5E5E3] dark:border-[#2A2A2D] text-[11px] font-mono text-[#111111] dark:text-[#EDEDEA] hover:border-[#475569] transition-colors"
      title="Toggle Light / Dark Monochrome Theme"
    >
      {isDark ? "Light Mode" : "Dark Mode"}
    </button>
  );
};

