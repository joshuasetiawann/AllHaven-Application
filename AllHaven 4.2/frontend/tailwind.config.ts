import type { Config } from "tailwindcss";

/**
 * AllHaven design system — "Aurora Glass" dark theme.
 * Near-black navy canvas (#06070E), frosted-glass panels, luminous
 * cyan→violet accents and slow-drifting aurora glow blobs. Tokens live as
 * CSS variables in globals.css; this file maps them onto Tailwind.
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
          DEFAULT: "rgb(var(--color-bg) / <alpha-value>)", // app canvas
          deep: "rgb(var(--color-bg-deep) / <alpha-value>)",
        },
        surface: {
          DEFAULT: "rgb(var(--color-surface) / <alpha-value>)", // panels
          raised: "rgb(var(--color-surface-raised) / <alpha-value>)", // hover / raised
          high: "rgb(var(--color-surface-high) / <alpha-value>)", // active nav, chips
          input: "rgb(var(--color-surface-input) / <alpha-value>)", // inputs
        },
        border: {
          DEFAULT: "rgb(var(--color-border) / <alpha-value>)", // hairline
          strong: "rgb(var(--color-border-strong) / <alpha-value>)",
        },
        primary: {
          DEFAULT: "rgb(var(--color-primary) / <alpha-value>)",
          dim: "rgb(var(--color-primary-dim) / <alpha-value>)",
          bright: "rgb(var(--color-primary-bright) / <alpha-value>)",
          fg: "rgb(var(--color-primary-fg) / <alpha-value>)",
        },
        secondary: {
          DEFAULT: "rgb(var(--color-secondary) / <alpha-value>)",
          soft: "rgb(var(--color-secondary-soft) / <alpha-value>)",
          deep: "rgb(var(--color-secondary-deep) / <alpha-value>)",
        },
        content: {
          DEFAULT: "rgb(var(--color-content) / <alpha-value>)", // primary text
          muted: "rgb(var(--color-content-muted) / <alpha-value>)", // secondary text
          subtle: "rgb(var(--color-content-subtle) / <alpha-value>)", // tertiary / metadata
          faint: "rgb(var(--color-content-faint) / <alpha-value>)", // timestamps, axis ticks
        },
        success: {
          DEFAULT: "rgb(var(--color-success) / <alpha-value>)",
          soft: "rgb(var(--color-success-soft) / <alpha-value>)",
        },
        warning: {
          DEFAULT: "rgb(var(--color-warning) / <alpha-value>)",
          deep: "rgb(var(--color-warning-deep) / <alpha-value>)",
        },
        danger: "rgb(var(--color-danger) / <alpha-value>)",
        info: "rgb(var(--color-info) / <alpha-value>)",
        magenta: "rgb(var(--color-magenta) / <alpha-value>)",
      },
      fontFamily: {
        sans: ["Geist", "Inter", "system-ui", "-apple-system", "Segoe UI", "sans-serif"],
        label: ["Geist", "Inter", "system-ui", "sans-serif"],
        mono: ["Geist Mono", "ui-monospace", "SFMono-Regular", "Menlo", "monospace"],
      },
      // Aurora radii — cards 18–20, tiles 16, buttons 11–14, icon tiles 9–13.
      borderRadius: {
        sm: "0.5rem", // 8
        DEFAULT: "0.625rem", // 10
        md: "0.75rem", // 12
        lg: "0.875rem", // 14
        xl: "1rem", // 16
        "2xl": "1.25rem", // 20
        "3xl": "1.625rem", // 26
      },
      boxShadow: {
        glow: "0 0 0 1px rgb(var(--color-primary) / 0.08), 0 24px 60px -24px rgba(0,0,0,0.72)",
        "glow-primary": "0 0 26px rgb(var(--color-primary) / 0.22)",
        panel: "0 24px 60px -24px rgba(0,0,0,0.72), inset 0 1px 0 rgba(255,255,255,0.08)",
        "btn-primary": "0 14px 30px -12px rgb(var(--color-primary) / 0.8), inset 0 1px 0 rgba(255,255,255,0.3)",
        "toggle-on": "0 0 14px rgb(var(--color-primary) / 0.3)",
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
        // Live status dots (Aurora spec).
        "pulse-glow": {
          "0%, 100%": { opacity: "0.45" },
          "50%": { opacity: "1" },
        },
        // Aurora blob drift.
        "aurora-drift": {
          "0%, 100%": { transform: "translate(0,0) scale(1)" },
          "50%": { transform: "translate(3%,2%) scale(1.06)" },
        },
        "float-y": {
          "0%, 100%": { transform: "translateY(0)" },
          "50%": { transform: "translateY(-6px)" },
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
        "pulse-glow": "pulse-glow 1.8s ease-in-out infinite",
        "aurora-drift": "aurora-drift 20s ease-in-out infinite",
        "float-y": "float-y 6s ease-in-out infinite",
      },
    },
  },
  plugins: [],
};

export default config;
