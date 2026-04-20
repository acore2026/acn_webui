/** @type {import('tailwindcss').Config} */
module.exports = {
  content: ['./src/**/*.{js,jsx,ts,tsx}'],
  theme: {
    extend: {
      boxShadow: {
        panel: '0 24px 60px rgba(8, 15, 52, 0.45)',
        glow: '0 0 0 1px rgba(96, 165, 250, 0.18), 0 20px 45px rgba(56, 189, 248, 0.14)'
      },
      colors: {
        canvas: {
          950: '#060816',
          900: '#0b1224',
          800: '#12203f'
        }
      },
      backgroundImage: {
        'dashboard-glow':
          'radial-gradient(circle at top left, rgba(34,197,94,0.12), transparent 28%), radial-gradient(circle at top right, rgba(59,130,246,0.16), transparent 32%), linear-gradient(180deg, rgba(10,16,35,0.98), rgba(3,8,22,1))'
      }
    }
  },
  plugins: []
}
