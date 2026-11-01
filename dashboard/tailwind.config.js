/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  darkMode: "class",
  theme: {
    extend: {
      colors: {
        iit: {
          navy: "#0B2545",
          blue: "#133E87",
          light: "#EEF4FB",
          surface: "#F8FAFC",
          card: "#FFFFFF",
          border: "#E2E8F0",
          crimson: "#B91C1C",
          crimsonLight: "#FEF2F2",
          text: "#0F172A",
          muted: "#475569",
        },
        status: {
          ok: "#15803D",
          okBg: "#F0FDF4",
          warning: "#B45309",
          warningBg: "#FFFBEB",
          critical: "#DC2626",
          criticalBg: "#FEF2F2",
        },
      },
      fontFamily: {
        sans: ["Inter", "-apple-system", "BlinkMacSystemFont", "Segoe UI", "Roboto", "sans-serif"],
        mono: ["JetBrains Mono", "ui-monospace", "SFMono-Regular", "monospace"],
      },
    },
  },
  plugins: [],
}
