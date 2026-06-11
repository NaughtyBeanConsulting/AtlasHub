/** @type {import('tailwindcss').Config} */
// Compiled with the standalone Tailwind CLI (no Node required):
//   ./build_tailwind.sh
// Output: static/css/tailwind.css (committed, served locally — no CDN).
//
// The palette mirrors the Atlassian Design System tokens:
//   blue  = ADS B50–B500 (brand), n = ADS neutrals N0–N900,
//   green/red/yellow/purple/teal = ADS accents used by Jira statuses,
//   priorities and issue types. Use these tokens — no inline hex in templates.
module.exports = {
  content: [
    './templates/**/*.html',
    './static/js/**/*.js',
  ],
  theme: {
    extend: {
      colors: {
        blue: {
          50: '#DEEBFF',   // B50
          100: '#B3D4FF',  // B75
          200: '#4C9AFF',  // B100
          300: '#2684FF',  // B200
          400: '#0065FF',  // B300
          500: '#0052CC',  // B400 — primary brand
          600: '#0747A6',  // B500
          700: '#053068',
        },
        // Flat keys on purpose: nested scales would generate `bg-n-20`;
        // these give `bg-n20`, `text-n800`, … matching ADS neutral names.
        n0: '#FFFFFF', n10: '#FAFBFC', n20: '#F4F5F7', n30: '#EBECF0',
        n40: '#DFE1E6', n50: '#C1C7D0', n60: '#B3BAC5', n70: '#A5ADBA',
        n80: '#97A0AF', n90: '#8993A4', n100: '#7A869A', n200: '#6B778C',
        n300: '#5E6C84', n400: '#505F79', n500: '#42526E', n600: '#344563',
        n700: '#253858', n800: '#172B4D', n900: '#091E42',
        green: { 50: '#E3FCEF', 300: '#57D9A3', 400: '#36B37E', 500: '#00875A', 600: '#006644' },
        red: { 50: '#FFEBE6', 300: '#FF7452', 400: '#FF5630', 500: '#DE350B', 600: '#BF2600' },
        yellow: { 50: '#FFFAE6', 300: '#FFC400', 400: '#FFAB00', 500: '#FF8B00' },
        purple: { 50: '#EAE6FF', 300: '#998DD9', 400: '#8777D9', 500: '#6554C0', 600: '#5243AA' },
        teal: { 50: '#E6FCFF', 300: '#79E2F2', 400: '#00C7E6', 500: '#00B8D9', 600: '#00A3BF' },
      },
      fontFamily: {
        sans: [
          '-apple-system', 'BlinkMacSystemFont', '"Segoe UI"', 'Roboto',
          '"Noto Sans"', 'Ubuntu', 'sans-serif',
        ],
      },
      boxShadow: {
        card: '0 1px 2px rgba(9, 30, 66, 0.25)',
        raised: '0 1px 1px rgba(9, 30, 66, 0.25), 0 0 1px rgba(9, 30, 66, 0.31)',
        overlay: '0 8px 16px -4px rgba(9, 30, 66, 0.25), 0 0 1px rgba(9, 30, 66, 0.31)',
      },
      maxWidth: {
        '8xl': '90rem',
      },
    },
  },
  plugins: [],
};
