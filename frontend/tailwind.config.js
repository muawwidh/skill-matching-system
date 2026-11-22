/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      fontFamily: {
        sans: ["Inter", "ui-sans-serif", "system-ui", "-apple-system", "Segoe UI", "sans-serif"],
        display: ['"Space Grotesk"', "Inter", "ui-sans-serif", "system-ui", "sans-serif"],
      },
      colors: {
        // Design tokens. ink/ocean/mist/ember keep their old names so every page picks up the new palette.
        ink: "#14202B",
        muted: "#5B6673",
        line: "#E3E7EC",
        mist: "#F6F7F9",
        ocean: "#0B6E66",
        ember: "#6B3A08",
        teal: { DEFAULT: "#0B6E66", hover: "#08534D", soft: "#E3F2F0", text: "#0B4F49" },
        caution: { bg: "#FDF0DC", text: "#6B3A08", line: "#C98A2B", bar: "#E8A23A" },
        miss: { bg: "#FCE8EC", text: "#8A1F31" },
        neutral: { bg: "#EEF1F4", text: "#3C4752", bar: "#DDE2E8" },
        night: { DEFAULT: "#14202B", muted: "#C3CCD5" },
      },
      borderRadius: { card: "16px" },
      maxWidth: { content: "1240px" },
    },
  },
  plugins: [],
};
