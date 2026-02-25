/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        navy: {
          900: '#0A0F1E',
          800: '#0D1428',
          700: '#111D3E',
          600: '#162347',
          500: '#1B2B5A',
        },
        electric: {
          500: '#3B82F6',
          400: '#60A5FA',
          300: '#93C5FD',
        },
        teal: {
          500: '#14B8A6',
          400: '#2DD4BF',
        }
      },
      fontFamily: {
        sans: ['Inter', 'system-ui', 'sans-serif'],
      }
    },
  },
  plugins: [],
}