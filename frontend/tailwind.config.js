/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  darkMode: 'class',
  theme: {
    extend: {
      colors: {
        ink: {
          50: '#f6f7f9',
          100: '#edeef2',
          200: '#d7dae2',
          300: '#b4bacb',
          400: '#8c96b0',
          500: '#6f7997',
          600: '#57607c',
          700: '#464d65',
          800: '#3c4154',
          900: '#1b1e28',
          950: '#0f1117',
        },
        parchment: {
          50: '#fdfbf7',
          100: '#f9f6ee',
          200: '#f1ede1',
          300: '#e5ded0',
          400: '#d3c7b3',
          500: '#bcac95',
          600: '#a39179',
          700: '#847461',
          800: '#6c5f50',
          900: '#584e43',
        },
        navy: {
          50: '#f0f5fa',
          100: '#deebf4',
          200: '#c2dbe9',
          300: '#98c3db',
          400: '#67a4c9',
          500: '#4588b3',
          600: '#356e98',
          700: '#2c587c',
          800: '#274b67',
          900: '#254057',
          950: '#162838',
        },
        forest: {
          50: '#f2f8f5',
          100: '#e1f0e8',
          200: '#c4e2d3',
          300: '#99ceb5',
          400: '#67b291',
          500: '#449673',
          600: '#34795c',
          700: '#2c614b',
          800: '#264e3e',
          900: '#214134',
        },
        accent: {
          amber: '#d97706',
          crimson: '#be123c',
        }
      },
      fontFamily: {
        sans: ['Inter', '-apple-system', 'BlinkMacSystemFont', 'Segoe UI', 'Roboto', 'sans-serif'],
        serif: ['Newsreader', 'Georgia', 'Cambria', 'serif'],
        mono: ['JetBrains Mono', 'Fira Code', 'monospace'],
      },
      boxShadow: {
        'subtle': '0 1px 2px 0 rgba(0, 0, 0, 0.04)',
        'card': '0 1px 3px 0 rgba(0, 0, 0, 0.05), 0 1px 2px -1px rgba(0, 0, 0, 0.05)',
        'elevated': '0 4px 6px -1px rgba(0, 0, 0, 0.07), 0 2px 4px -2px rgba(0, 0, 0, 0.05)',
      }
    },
  },
  plugins: [],
}
