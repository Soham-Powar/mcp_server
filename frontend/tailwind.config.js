/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        sidebar: "#171717",
        surface: "#212121",
        bubble: "#2f2f2f",
      },
    },
  },
  plugins: [],
};
