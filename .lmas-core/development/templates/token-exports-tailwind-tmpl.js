/**
 * LMAS Design Token Exports — Tailwind CSS Theme Configuration
 * Template ID: token-exports-tailwind
 * Version: 1.0.0 | Created: 2026-03-17
 * Used by: @ux-design-expert (Switch), @dev (Neo)
 *
 * Generated from tokens-schema-tmpl.yaml.
 * Import in tailwind.config.js: const tokens = require('./path/to/this/file')
 * Then spread into theme.extend: theme: { extend: { ...tokens } }
 *
 * All values reference CSS custom properties so themes can be swapped at runtime.
 */

/** @type {import('tailwindcss').Config['theme']} */
module.exports = {
  colors: {
    // Primitive — use semantic tokens in components instead
    white: 'var(--color-white, #FFFFFF)',
    black: 'var(--color-black, #000000)',

    gray: {
      50:  'var(--color-gray-50, #F9FAFB)',
      100: 'var(--color-gray-100, #F3F4F6)',
      200: 'var(--color-gray-200, #E5E7EB)',
      300: 'var(--color-gray-300, #D1D5DB)',
      400: 'var(--color-gray-400, #9CA3AF)',
      500: 'var(--color-gray-500, #6B7280)',
      600: 'var(--color-gray-600, #4B5563)',
      700: 'var(--color-gray-700, #374151)',
      800: 'var(--color-gray-800, #1F2937)',
      900: 'var(--color-gray-900, #111827)',
    },

    // Semantic tokens — preferred for component usage
    primary:   'var(--color-primary, #2563EB)',
    secondary: 'var(--color-secondary, #4B5563)',
    surface:   'var(--color-surface, #FFFFFF)',
    background: 'var(--color-background, #F3F4F6)',
    border:    'var(--color-border, #E5E7EB)',

    error:   'var(--color-error, #EF4444)',
    success: 'var(--color-success, #22C55E)',
    warning: 'var(--color-warning, #F59E0B)',
    info:    'var(--color-info, #3B82F6)',

    'text-primary':   'var(--color-text-primary, #111827)',
    'text-secondary': 'var(--color-text-secondary, #6B7280)',
    'text-inverse':   'var(--color-text-inverse, #FFFFFF)',
  },

  fontFamily: {
    heading: ['var(--font-heading)', 'Inter', 'system-ui', '-apple-system', 'sans-serif'],
    body:    ['var(--font-body)', 'Inter', 'system-ui', '-apple-system', 'sans-serif'],
    mono:    ['var(--font-mono)', 'JetBrains Mono', 'Fira Code', 'monospace'],
  },

  fontSize: {
    xs:   ['var(--font-size-xs, 0.75rem)',   { lineHeight: 'var(--line-height-normal, 1.5)' }],
    sm:   ['var(--font-size-sm, 0.875rem)',  { lineHeight: 'var(--line-height-normal, 1.5)' }],
    base: ['var(--font-size-base, 1rem)',    { lineHeight: 'var(--line-height-normal, 1.5)' }],
    lg:   ['var(--font-size-lg, 1.125rem)',  { lineHeight: 'var(--line-height-normal, 1.5)' }],
    xl:   ['var(--font-size-xl, 1.25rem)',   { lineHeight: 'var(--line-height-tight, 1.25)' }],
    '2xl': ['var(--font-size-2xl, 1.5rem)',  { lineHeight: 'var(--line-height-tight, 1.25)' }],
    '3xl': ['var(--font-size-3xl, 1.875rem)', { lineHeight: 'var(--line-height-tight, 1.25)' }],
    '4xl': ['var(--font-size-4xl, 2.25rem)', { lineHeight: 'var(--line-height-tight, 1.25)' }],
  },

  spacing: {
    0:  'var(--spacing-0, 0px)',
    1:  'var(--spacing-1, 4px)',
    2:  'var(--spacing-2, 8px)',
    3:  'var(--spacing-3, 12px)',
    4:  'var(--spacing-4, 16px)',
    5:  'var(--spacing-5, 20px)',
    6:  'var(--spacing-6, 24px)',
    8:  'var(--spacing-8, 32px)',
    10: 'var(--spacing-10, 40px)',
    12: 'var(--spacing-12, 48px)',
    16: 'var(--spacing-16, 64px)',
    20: 'var(--spacing-20, 80px)',
  },

  borderRadius: {
    none: 'var(--border-radius-none, 0px)',
    sm:   'var(--border-radius-sm, 4px)',
    DEFAULT: 'var(--border-radius-md, 8px)',
    md:   'var(--border-radius-md, 8px)',
    lg:   'var(--border-radius-lg, 12px)',
    xl:   'var(--border-radius-xl, 16px)',
    full: 'var(--border-radius-full, 9999px)',
  },

  boxShadow: {
    none: 'var(--shadow-none, none)',
    sm:   'var(--shadow-sm, 0 1px 2px 0 rgba(0,0,0,0.05))',
    DEFAULT: 'var(--shadow-md, 0 4px 6px -1px rgba(0,0,0,0.1))',
    md:   'var(--shadow-md, 0 4px 6px -1px rgba(0,0,0,0.1))',
    lg:   'var(--shadow-lg, 0 10px 15px -3px rgba(0,0,0,0.1))',
    xl:   'var(--shadow-xl, 0 20px 25px -5px rgba(0,0,0,0.1))',
  },

  screens: {
    sm:  '640px',
    md:  '768px',
    lg:  '1024px',
    xl:  '1280px',
    '2xl': '1536px',
  },

  transitionDuration: {
    0:       'var(--motion-duration-instant, 0ms)',
    fast:    'var(--motion-duration-fast, 100ms)',
    DEFAULT: 'var(--motion-duration-normal, 200ms)',
    slow:    'var(--motion-duration-slow, 300ms)',
    slower:  'var(--motion-duration-slower, 500ms)',
  },

  transitionTimingFunction: {
    DEFAULT:    'var(--motion-easing-default)',
    'ease-in':  'var(--motion-easing-ease-in)',
    'ease-out': 'var(--motion-easing-ease-out)',
    spring:     'var(--motion-easing-spring)',
  },
}
