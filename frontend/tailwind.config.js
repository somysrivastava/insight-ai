/** @type {import('tailwindcss').Config} */
export default {
  darkMode: 'class',
  content: ['./index.html', './src/**/*.{js,ts,jsx,tsx}'],
  theme: {
    extend: {
      colors: {
        // InsightAI brand palette — dark theme only for Day 26 (demo-optimized,
        // not a themeable app). "brand" is the indigo accent used for primary
        // actions/links/active nav; "surface" is card/panel backgrounds one
        // step lighter than the page background, so cards read as elevated
        // without needing a shadow (shadows barely read on a dark background).
        brand: {
          50: '#eef2ff',
          100: '#e0e7ff',
          200: '#c7d2fe',
          300: '#a5b4fc',
          400: '#818cf8',
          500: '#6366f1',
          600: '#4f46e5',
          700: '#4338ca',
          800: '#3730a3',
          900: '#312e81',
        },
        background: '#0b0e14',
        surface: '#131722',
        'surface-hover': '#1a1f2e',
        border: '#232838',
      },
      fontFamily: {
        sans: ['Inter', 'ui-sans-serif', 'system-ui', 'sans-serif'],
      },
    },
  },
  plugins: [],
}
