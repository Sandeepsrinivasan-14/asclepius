import type { Config } from "tailwindcss";

const config: Config = {
  content: ["./app/**/*.{ts,tsx}", "./components/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        ink: { 950: "#04070d", 900: "#070c16", 800: "#0b1220", 700: "#111a2c", 600: "#18243b", 500: "#22314d" },
        jade: { 300: "#6ee7c8", 400: "#34d6ae", 500: "#10c295", 600: "#0a9d77" },
        aur: { gold: "#f2c46d", rose: "#ff7a90", violet: "#8b7bff", sky: "#5cc8ff", amber: "#ffb454" },
      },
      fontFamily: {
        sans: ["var(--font-sans)", "ui-sans-serif", "system-ui"],
        display: ["var(--font-display)", "ui-serif", "Georgia"],
        mono: ["var(--font-mono)", "ui-monospace", "monospace"],
      },
      boxShadow: {
        glow: "0 0 0 1px rgba(110,231,200,.18), 0 10px 40px -10px rgba(16,194,149,.35)",
        card: "0 1px 0 0 rgba(255,255,255,.04) inset, 0 20px 50px -25px rgba(0,0,0,.8)",
      },
      keyframes: {
        float: { "0%,100%": { transform: "translateY(0)" }, "50%": { transform: "translateY(-8px)" } },
        shimmer: { "0%": { backgroundPosition: "-200% 0" }, "100%": { backgroundPosition: "200% 0" } },
        pulseRing: { "0%": { transform: "scale(.8)", opacity: ".8" }, "100%": { transform: "scale(2.2)", opacity: "0" } },
        drift: { "0%": { transform: "translate3d(0,0,0)" }, "50%": { transform: "translate3d(40px,-30px,0)" }, "100%": { transform: "translate3d(0,0,0)" } },
        scan: { "0%": { transform: "translateY(-100%)" }, "100%": { transform: "translateY(100%)" } },
      },
      animation: {
        float: "float 6s ease-in-out infinite", shimmer: "shimmer 3s linear infinite", pulseRing: "pulseRing 1.8s ease-out infinite",
        drift: "drift 18s ease-in-out infinite", scan: "scan 3.5s linear infinite",
      },
    },
  },
  plugins: [],
};
export default config;
