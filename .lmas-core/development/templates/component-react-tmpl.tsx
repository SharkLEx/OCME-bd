/**
 * LMAS React Component Template
 * Template ID: component-react
 * Version: 1.0.0 | Created: 2026-03-17
 * Used by: @ux-design-expert (Switch), @dev (Neo)
 *
 * Instructions:
 * 1. Replace {{ComponentName}} with the actual component name (PascalCase)
 * 2. Replace {{component-name}} with kebab-case equivalent
 * 3. Define props in the interface below
 * 4. Implement component logic in the body
 * 5. Remove this comment block after scaffolding
 */

import * as React from 'react'

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

/**
 * Variant options for visual appearance.
 * Extend this union as the design system grows.
 */
type ComponentVariant = 'default' | 'primary' | 'secondary' | 'ghost'

/**
 * Size options following the spacing scale tokens.
 */
type ComponentSize = 'sm' | 'md' | 'lg'

/**
 * Props interface for {{ComponentName}}.
 *
 * Follows compound-component pattern:
 * - Extends native HTML attributes for the root element
 * - Exposes design-system variants as typed props
 * - Supports `ref` forwarding via `React.forwardRef`
 */
export interface ComponentNameProps
  extends React.HTMLAttributes<HTMLDivElement> {
  /** Visual variant controlling color scheme and emphasis */
  variant?: ComponentVariant
  /** Size controlling padding, font size, and min dimensions */
  size?: ComponentSize
  /** Disables interaction and applies muted styles */
  disabled?: boolean
  /** Content rendered inside the component */
  children: React.ReactNode
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

/**
 * {{ComponentName}} — {{Brief description of what this component does}}.
 *
 * @example
 * ```tsx
 * <ComponentName variant="primary" size="md">
 *   Content here
 * </ComponentName>
 * ```
 *
 * @see {@link ComponentNameProps} for all available props
 */
const ComponentName = React.forwardRef<HTMLDivElement, ComponentNameProps>(
  (
    {
      variant = 'default',
      size = 'md',
      disabled = false,
      children,
      className,
      ...rest
    },
    ref
  ) => {
    // Map variant and size to CSS custom property classes.
    // Uses design tokens via CSS custom properties — no hardcoded values.
    const rootStyles: React.CSSProperties = {
      // Colors from semantic tokens
      color: `var(--color-text-primary)`,
      backgroundColor: `var(--color-surface)`,
      borderColor: `var(--color-border)`,
      borderWidth: 'var(--border-width-thin)',
      borderStyle: 'solid',
      borderRadius: `var(--border-radius-md)`,

      // Size-dependent spacing from token scale
      padding:
        size === 'sm'
          ? 'var(--spacing-1) var(--spacing-2)'
          : size === 'lg'
            ? 'var(--spacing-4) var(--spacing-6)'
            : 'var(--spacing-2) var(--spacing-4)',

      fontSize:
        size === 'sm'
          ? 'var(--font-size-sm)'
          : size === 'lg'
            ? 'var(--font-size-lg)'
            : 'var(--font-size-base)',

      // Transition using motion tokens
      transition: 'all var(--motion-duration-normal) var(--motion-easing-default)',

      // Disabled state
      opacity: disabled ? 0.5 : 1,
      pointerEvents: disabled ? 'none' : 'auto',
      cursor: disabled ? 'not-allowed' : 'pointer',
    }

    return (
      <div
        ref={ref}
        role="region"
        aria-disabled={disabled || undefined}
        data-variant={variant}
        data-size={size}
        style={rootStyles}
        className={className}
        {...rest}
      >
        {children}
      </div>
    )
  }
)

ComponentName.displayName = 'ComponentName'

export default ComponentName
