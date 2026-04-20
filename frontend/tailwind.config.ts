import type { Config } from "tailwindcss";

const config: Config = {
  content: ["./index.html", "./src/**/*.{js,ts,jsx,tsx}"],
  darkMode: "class",
  theme: {
    extend: {
      colors: {
        bg: {
          base: "var(--bg-base)",
          surface: "var(--bg-surface)",
          elevated: "var(--bg-elevated)",
          overlay: "var(--bg-overlay)",
        },
        border: {
          subtle: "var(--border-subtle)",
          DEFAULT: "var(--border-default)",
          strong: "var(--border-strong)",
        },
        text: {
          primary: "var(--text-primary)",
          secondary: "var(--text-secondary)",
          tertiary: "var(--text-tertiary)",
          inverse: "var(--text-inverse)",
        },
        brand: {
          50: "var(--brand-50)",
          100: "var(--brand-100)",
          400: "var(--brand-400)",
          500: "var(--brand-500)",
          600: "var(--brand-600)",
          900: "var(--brand-900)",
        },
        success: { 500: "var(--success-500)", 900: "var(--success-900)" },
        warning: { 500: "var(--warning-500)", 900: "var(--warning-900)" },
        danger: { 500: "var(--danger-500)", 900: "var(--danger-900)" },
        info: { 500: "var(--info-500)", 900: "var(--info-900)" },
        node: {
          person: "var(--node-person)",
          company: "var(--node-company)",
          email: "var(--node-email)",
          phone: "var(--node-phone)",
          username: "var(--node-username)",
          ip: "var(--node-ip)",
          domain: "var(--node-domain)",
        },
      },
      fontFamily: {
        sans: ["var(--font-sans)"],
        mono: ["var(--font-mono)"],
      },
      borderRadius: {
        sm: "var(--radius-sm)",
        md: "var(--radius-md)",
        lg: "var(--radius-lg)",
        xl: "var(--radius-xl)",
      },
      boxShadow: {
        sm: "var(--shadow-sm)",
        md: "var(--shadow-md)",
        lg: "var(--shadow-lg)",
        glow: "var(--shadow-glow)",
      },
    },
  },
  plugins: [],
};

export default config;
