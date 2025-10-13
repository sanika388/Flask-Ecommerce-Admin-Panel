// tailwind.config.js

/** @type {import('tailwindcss').Config} */
module.exports = {
  // CRITICAL: Look for utility classes in all HTML files
  content: [
    "./templates/**/*.html",
  ],
  theme: {
    extend: {
      // CRITICAL: Define our custom Royal Purple color
      colors: {
        'royal-purple': '#6A0DAD', // The primary deep purple color
        'light-purple': '#8A2BE2', // A lighter shade for hover/accents
        'bg-light': '#F5F5F5',     // The light grey background for the main content area
        'status-green': '#34D399', // Custom status green
        'status-yellow': '#FBBF24', // Custom status yellow/pending
        'status-red': '#EF4444',   // Custom status red/suspended
      },
      // Define custom box shadow to match the UI card styling
      boxShadow: {
        'card': '0 1px 3px 0 rgba(0, 0, 0, 0.1), 0 1px 2px 0 rgba(0, 0, 0, 0.06)', 
        'login': '0 10px 25px rgba(0, 0, 0, 0.3)', // Stronger shadow for the login box
      }
    },
  },
  plugins: [],
}