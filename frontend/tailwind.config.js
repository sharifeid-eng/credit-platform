/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{js,jsx,ts,tsx}'],
  theme: {
    extend: {
      colors: {
        // Backgrounds
        base:    '#0C1018',
        surface: '#111620',
        nav:     '#080B12',
        deep:    '#050810',

        // Borders
        border:  '#1E2736',

        // Brand
        gold:    '#C9A84C',
        'gold-dim': '#8A6D2E',

        // Metrics
        teal:    '#2DD4BF',
        red:     '#F06060',
        blue:    '#5B8DEF',

        // Text
        primary:   '#E8EAF0',
        secondary: '#8A94A8',
        muted:     '#4A5568',
        faint:     '#2A3548',
      },
      fontFamily: {
        ui:   ['Inter', 'system-ui', 'sans-serif'],
        mono: ['"IBM Plex Mono"', '"Courier New"', 'monospace'],
      },
      fontSize: {
        '2xs': ['9px',  { lineHeight: '1.4', letterSpacing: '0.1em' }],
        xs:    ['11px', { lineHeight: '1.5' }],
        sm:    ['12px', { lineHeight: '1.5' }],
        base:  ['13px', { lineHeight: '1.6' }],
        lg:    ['15px', { lineHeight: '1.5' }],
        xl:    ['18px', { lineHeight: '1.3' }],
        '2xl': ['22px', { lineHeight: '1.2' }],
        '3xl': ['28px', { lineHeight: '1.1' }],
      },
      borderRadius: {
        sm: '6px',
        md: '10px',
        lg: '14px',
      },
      boxShadow: {
        card:      '0 1px 3px rgba(0,0,0,0.4), 0 0 0 1px #1E2736',
        'glow-gold': '0 0 16px rgba(201,168,76,0.2)',
        'glow-teal': '0 0 8px rgba(45,212,191,0.3)',
      },
    },
  },
  plugins: [],
}