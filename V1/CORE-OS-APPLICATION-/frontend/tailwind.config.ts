import type { Config } from "tailwindcss";

/**
 * CoreOS design system.
 * Tokens are derived from the Stitch "CoreOS Command Center" design:
 * a matte "Deep Night" palette, electric-cyan primary, muted-royal secondary,
 * 1px hairline borders, and subtle glass panels.
 */
const config: Config = {
  content: [
    "./app/**/*.{ts,tsx}",
    "./components/**/*.{ts,tsx}",
    "./features/**/*.{ts,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        bg: "#0B0E14", // Level 0 background (Deep Night)
        surface: {
          DEFAULT: "#161B22", // Level 1 panels
          raised: "#1C2128", // hover / raised
          high: "#21262D",
          input: "#0B0E14", // inputs are darker than panels
        },
        border: {
          DEFAULT: "#30363D", // hairline
          strong: "#3D444D",
        },
        primary: {
          DEFAULT: "#00F5FF", // electric cyan
          dim: "#00DCE5",
          fg: "#00282B", // text on primary
        },
        secondary: {
          DEFAULT: "#8A2BE2", // muted royal
          soft: "#DCB8FF",
        },
        content: {
          DEFAULT: "#E1E2EB", // on-surface
          muted: "#9AA7B2", // on-surface-variant
          subtle: "#6E7681",
        },
        success: "#3FB950",
        warning: "#D29922",
        danger: "#F85149",
      },
      fontFamily: {
        sans: ["Inter", "system-ui", "-apple-system", "Segoe UI", "sans-serif"],
        label: ["Geist", "Inter", "system-ui", "sans-serif"],
        mono: ["Geist Mono", "ui-monospace", "SFMono-Regular", "Menlo", "monospace"],
      },
      borderRadius: {
        sm: "0.125rem",
        DEFAULT: "0.25rem",
        md: "0.375rem",
        lg: "0.5rem",
        xl: "0.75rem",
      },
      boxShadow: {
        glow: "0 0 0 1px rgba(0,245,255,0.05), 0 8px 30px rgba(0,0,0,0.35)",
      },
      backdropBlur: {
        panel: "12px",
      },
      keyframes: {
        "fade-in": {
          "0%": { opacity: "0", transform: "translateY(4px)" },
          "100%": { opacity: "1", transform: "translateY(0)" },
        },
        "pulse-soft": {
          "0%, 100%": { opacity: "1" },
          "50%": { opacity: "0.4" },
        },
      },
      animation: {
        "fade-in": "fade-in 0.2s ease-out",
        "pulse-soft": "pulse-soft 2s ease-in-out infinite",
      },
    },
  },
  plugins: [],
};

export default config;
