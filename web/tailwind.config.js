const c = (v) => `rgb(var(--${v}) / <alpha-value>)`;
/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  darkMode: "class",
  theme: {
    extend: {
      colors: {
        bg: c("bg"), surface: c("surface"), surface2: c("surface2"), ink: c("ink"), muted: c("muted"),
        line: c("line"), accent: c("accent"), "accent-ink": c("accent-ink"), "accent-soft": c("accent-soft"),
        low: c("low"), mid: c("mid"), high: c("high"),
      },
      fontFamily: {
        sans: ['"Inter Variable"', "ui-sans-serif", "system-ui", "-apple-system", "Segoe UI", "sans-serif"],
        display: ['"Fraunces Variable"', "ui-serif", "Georgia", "serif"],
      },
      boxShadow: { card: "0 1px 2px rgb(var(--shadow) / .06), 0 8px 24px -12px rgb(var(--shadow) / .14)" },
      borderRadius: { xl2: "1.125rem" },
    },
  },
  plugins: [],
};
