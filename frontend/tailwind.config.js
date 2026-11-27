/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      fontFamily: {
        sans: ['"Instrument Sans"', "ui-sans-serif", "system-ui", "-apple-system", "Segoe UI", "sans-serif"],
        display: ['"Bricolage Grotesque Variable"', '"Instrument Sans"', "ui-sans-serif", "system-ui", "sans-serif"],
      },
      colors: {
        // Design v2 (2026-11-27). Colour carries meaning only: have / related / gap / not needed.
        ink: "#12161C",
        muted: "#626B78",
        line: "#E6E9EE",
        mist: "#F6F7F9",
        have: { DEFAULT: "#0F8A6A", bg: "#E3F5EE", text: "#0B6B52" },
        related: { DEFAULT: "#6D4AE0", bg: "#F0ECFF", text: "#5536C4" },
        gap: { DEFAULT: "#E8590C", bg: "#FFF0E6", text: "#9A3412" },
        idle: { DEFAULT: "#DCE1E7", text: "#4A525E" },
        // Older token names, kept so every page picks up the new palette.
        ocean: "#12161C",
        ember: "#9A3412",
        teal: { DEFAULT: "#0F8A6A", hover: "#0B6E55", soft: "#E3F5EE", text: "#0B6B52" },
        caution: { bg: "#FFF0E6", text: "#9A3412", line: "#F4B184", bar: "#E8590C" },
        miss: { bg: "#FDECEC", text: "#B42318" },
        neutral: { bg: "#F0F2F5", text: "#3F4753", bar: "#E6E9EE" },
        night: { DEFAULT: "#12161C", muted: "#B8C0CC" },
      },
      borderRadius: { card: "14px" },
      maxWidth: { content: "1280px" },
      keyframes: {
        rise: { from: { opacity: "0", transform: "translateY(8px)" }, to: { opacity: "1", transform: "none" } },
        fill: { from: { transform: "scaleX(0)" }, to: { transform: "scaleX(1)" } },
        glow: {
          "0%, 100%": { boxShadow: "0 0 0 0 rgba(232, 89, 12, 0)" },
          "50%": { boxShadow: "0 0 0 6px rgba(232, 89, 12, 0.28)" },
        },
      },
      animation: {
        rise: "rise 360ms cubic-bezier(0.2, 0.7, 0.2, 1) both",
        fill: "fill 520ms cubic-bezier(0.2, 0.7, 0.2, 1) both",
        glow: "glow 900ms ease-in-out 2",
      },
    },
  },
  plugins: [],
};
