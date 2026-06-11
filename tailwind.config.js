/** @type {import('tailwindcss').Config} */
// Compiled with the standalone Tailwind CLI (no Node required):
//   ./build_tailwind.sh
// Output: static/css/tailwind.css (committed, served locally — no CDN).
//
// Every colour token resolves through a CSS variable (RGB triplets defined in
// static/src/tailwind.css for :root and .dark), so the whole app re-themes
// for dark mode without touching a single template class. The palette mirrors
// the Atlassian Design System: blue = brand, n* = neutrals N0–N900,
// green/red/yellow/purple/teal = the accents used by statuses, priorities and
// issue types. Use these tokens — no inline hex in templates.
const v = (name) => `rgb(var(--${name}) / <alpha-value>)`;

module.exports = {
  darkMode: 'class',
  content: [
    './templates/**/*.html',
    './static/js/**/*.js',
  ],
  theme: {
    extend: {
      colors: {
        blue: {
          50: v('blue-50'), 100: v('blue-100'), 200: v('blue-200'),
          300: v('blue-300'), 400: v('blue-400'), 500: v('blue-500'),
          600: v('blue-600'), 700: v('blue-700'),
        },
        // Flat keys on purpose: nested scales would generate `bg-n-20`;
        // these give `bg-n20`, `text-n800`, … matching ADS neutral names.
        n0: v('n0'), n10: v('n10'), n20: v('n20'), n30: v('n30'),
        n40: v('n40'), n50: v('n50'), n60: v('n60'), n70: v('n70'),
        n80: v('n80'), n90: v('n90'), n100: v('n100'), n200: v('n200'),
        n300: v('n300'), n400: v('n400'), n500: v('n500'), n600: v('n600'),
        n700: v('n700'), n800: v('n800'), n900: v('n900'),
        green: { 50: v('green-50'), 300: v('green-300'), 400: v('green-400'), 500: v('green-500'), 600: v('green-600') },
        red: { 50: v('red-50'), 300: v('red-300'), 400: v('red-400'), 500: v('red-500'), 600: v('red-600') },
        yellow: { 50: v('yellow-50'), 300: v('yellow-300'), 400: v('yellow-400'), 500: v('yellow-500') },
        purple: { 50: v('purple-50'), 300: v('purple-300'), 400: v('purple-400'), 500: v('purple-500'), 600: v('purple-600') },
        teal: { 50: v('teal-50'), 300: v('teal-300'), 400: v('teal-400'), 500: v('teal-500'), 600: v('teal-600') },
      },
      fontFamily: {
        sans: [
          '-apple-system', 'BlinkMacSystemFont', '"Segoe UI"', 'Roboto',
          '"Noto Sans"', 'Ubuntu', 'sans-serif',
        ],
      },
      boxShadow: {
        card: 'var(--sh-card)',
        raised: 'var(--sh-raised)',
        overlay: 'var(--sh-overlay)',
      },
      maxWidth: {
        '8xl': '90rem',
      },
    },
  },
  plugins: [],
};
