import type { Config } from "tailwindcss";

/**
 * AllHaven design system — "Command Center" premium dark theme.
 * Near-black canvas, refined teal-cyan primary, muted-purple secondary,
 * hairline borders, restrained glass panels. Tuned to the provided screens.
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
        bg: {
          DEFAULT: "#0A0C10", // app canvas (near-black, slight blue)
          deep: "#070809",
        },
        surface: {
          DEFAULT: "#10151C", // panels
          raised: "#161C25", // hover / raised
          high: "#1B2330", // active nav, chips
          input: "#0B0F15", // inputs darker than panels
        },
        border: {
          DEFAULT: "#1F2730", // hairline
          strong: "#2C3744",
        },
        primary: {
          DEFAULT: "#18E0D6", // signature teal-cyan
          dim: "#12C2BA",
          bright: "#54EEE6",
          fg: "#04201F", // text on primary
        },
        secondary: {
          DEFAULT: "#8B5CF6", // muted royal purple
          soft: "#C4B5FD",
        },
        content: {
          DEFAULT: "#E6EAF1", // primary text
          muted: "#8B96A7", // secondary text
          subtle: "#5C6877", // tertiary / metadata
        },
        success: "#34D399",
        warning: "#FBBF24",
        danger: "#F87171",
        info: "#38BDF8",
      },
      fontFamily: {
        sans: ["Inter", "system-ui", "-apple-system", "Segoe UI", "sans-serif"],
        label: ["Geist", "Inter", "system-ui", "sans-serif"],
        mono: ["Geist Mono", "ui-monospace", "SFMono-Regular", "Menlo", "monospace"],
      },
      borderRadius: {
        sm: "0.25rem",
        DEFAULT: "0.375rem",
        md: "0.5rem",
        lg: "0.625rem",
        xl: "0.875rem",
        "2xl": "1.125rem",
      },
      boxShadow: {
        glow: "0 0 0 1px rgba(24,224,214,0.08), 0 10px 40px rgba(0,0,0,0.45)",
        "glow-primary": "0 0 24px rgba(24,224,214,0.35)",
        panel: "0 1px 0 0 rgba(255,255,255,0.02) inset, 0 12px 40px -12px rgba(0,0,0,0.6)",
      },
      transitionTimingFunction: {
        // Soft, premium ease-out (easeOutExpo-ish) used across micro-interactions.
        soft: "cubic-bezier(0.16, 1, 0.3, 1)",
      },
      keyframes: {
        "fade-in": {
          "0%": { opacity: "0", transform: "translateY(6px)" },
          "100%": { opacity: "1", transform: "translateY(0)" },
        },
        "scale-in": {
          "0%": { opacity: "0", transform: "scale(0.97)" },
          "100%": { opacity: "1", transform: "scale(1)" },
        },
        // Dropdown / popover entrance (anchor with origin-top).
        pop: {
          "0%": { opacity: "0", transform: "scale(0.96) translateY(-4px)" },
          "100%": { opacity: "1", transform: "scale(1) translateY(0)" },
        },
        // Route / page content entrance.
        "page-in": {
          "0%": { opacity: "0", transform: "translateY(8px)" },
          "100%": { opacity: "1", transform: "translateY(0)" },
        },
        // Bottom-anchored entrance (pending-action panel, toasts).
        "slide-up": {
          "0%": { opacity: "0", transform: "translateY(10px)" },
          "100%": { opacity: "1", transform: "translateY(0)" },
        },
        "pulse-soft": {
          "0%, 100%": { opacity: "1" },
          "50%": { opacity: "0.35" },
        },
        shimmer: {
          "100%": { transform: "translateX(100%)" },
        },
      },
      animation: {
        "fade-in": "fade-in 0.22s cubic-bezier(0.16, 1, 0.3, 1)",
        "scale-in": "scale-in 0.16s cubic-bezier(0.16, 1, 0.3, 1)",
        pop: "pop 0.16s cubic-bezier(0.16, 1, 0.3, 1)",
        "page-in": "page-in 0.24s cubic-bezier(0.16, 1, 0.3, 1)",
        "slide-up": "slide-up 0.2s cubic-bezier(0.16, 1, 0.3, 1)",
        "pulse-soft": "pulse-soft 2s ease-in-out infinite",
      },
    },
  },
  plugins: [],
};

export default config;
