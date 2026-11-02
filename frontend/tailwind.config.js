/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        'neo-black': '#24314b',
        'neo-white': '#f2f4f9',
        'neo-gray': '#3e4d68',
        'neo-border': '#5d6b83',
        'neo-accent': '#6a58c5',
        'ui-border': '#dce3ef',
        'ui-muted': '#5d6b83',
        'ui-primary': '#4256be',
        'ui-primary-hover': '#35479f',
        'ui-primary-text': '#354b9c',
        'ui-accent-soft': '#eeeafa',
        'ui-accent-text': '#5b439d',
        'ui-context': '#eef1fc',
        'ui-context-border': '#d9e0f5',
        'ui-table-head': '#f0f3fa',
        'ui-nav': '#1c2946',
        'ui-nav-hover': '#273959',
        'ui-nav-active': '#334872',
        'ui-nav-text': '#d5dded',
        'ui-nav-muted': '#a1b0ce',
        'ui-nav-border': '#3b4b6b',
      },
      fontFamily: {
        'mono': ['Cascadia Code', 'Consolas', 'monospace'],
        'sans': ['Segoe UI', 'system-ui', 'sans-serif'],
      },
      borderWidth: {
        '3': '3px',
      },
    },
  },
  plugins: [],
}
