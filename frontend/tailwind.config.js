/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        ink: "#17202a",
        ocean: "#0f766e",
        ember: "#b45309",
        mist: "#f5f7fa",
      },
    },
  },
  plugins: [],
};
