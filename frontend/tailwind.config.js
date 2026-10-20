/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        'neo-black': '#0a0a0a',
        'neo-white': '#fafafa',
        'neo-gray': '#1a1a1a',
        'neo-border': '#333333',
        'neo-accent': '#ff6b35',
      },
      fontFamily: {
        'mono': ['IBM Plex Mono', 'monospace'],
        'sans': ['IBM Plex Sans', 'sans-serif'],
      },
      borderWidth: {
        '3': '3px',
      },
    },
  },
  plugins: [],
}
