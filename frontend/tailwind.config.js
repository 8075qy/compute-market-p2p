/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{vue,js,ts,jsx,tsx}",
  ],
  darkMode: 'class',
  theme: {
    extend: {
      colors: {
        primary: {
          DEFAULT: '#22D3EE',
          ink: '#05182A',
        },
        bg: '#0B1120',
        surface: '#131B2B',
        line: '#1F2A3A',
        lineHover: '#33415C',
        muted: '#8B97A8',
        success: '#34D399',
        warning: '#FBBF24',
        danger: '#F87171',
        accent: '#38BDF8',
      },
      fontFamily: {
        sans: ['PingFang SC', 'HarmonyOS Sans SC', 'MiSans', 'Microsoft YaHei', 'system-ui', 'sans-serif'],
        mono: ['Inter', '-apple-system', 'Menlo', 'monospace'],
      },
      borderRadius: {
        'card': '8px',
        'modal': '12px',
        'panel': '16px',
        'pill': '999px',
      },
      boxShadow: {
        'sm': '0 1px 3px rgba(15,23,42,.45)',
        'md': '0 10px 25px -5px rgba(0,0,0,.35)',
      },
      spacing: {
        '4': '4px',
        '8': '8px',
        '12': '12px',
        '16': '16px',
        '24': '24px',
        '32': '32px',
        '48': '48px',
        '64': '64px',
      },
    },
  },
  plugins: [],
}