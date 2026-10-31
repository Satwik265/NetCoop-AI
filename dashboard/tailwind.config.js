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
        light: {
          bg: "#FAFAF9",
          surface: "#FFFFFF",
          border: "#E5E5E3",
          text: "#111111",
          muted: "#6B6B66",
        },
        dark: {
          bg: "#0F0F10",
          surface: "#161618",
          border: "#2A2A2D",
          text: "#EDEDEA",
          muted: "#888884",
        },
        slate: {
          accent: "#475569",
        },
        status: {
          ok: "#5E7A6A",
          warning: "#A08A5B",
          critical: "#9A5B5B",
        },
      },
      fontFamily: {
        sans: ["Inter", "-apple-system", "BlinkMacSystemFont", "Segoe UI", "sans-serif"],
        mono: ["JetBrains Mono", "ui-monospace", "SFMono-Regular", "monospace"],
      },
    },
  },
  plugins: [],
}

