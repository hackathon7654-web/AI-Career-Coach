---
name: ProofPath AI
colors:
  surface: '#f7f9fb'
  surface-dim: '#d8dadc'
  surface-bright: '#f7f9fb'
  surface-container-lowest: '#ffffff'
  surface-container-low: '#f2f4f6'
  surface-container: '#eceef0'
  surface-container-high: '#e6e8ea'
  surface-container-highest: '#e0e3e5'
  on-surface: '#191c1e'
  on-surface-variant: '#44474e'
  inverse-surface: '#2d3133'
  inverse-on-surface: '#eff1f3'
  outline: '#74777f'
  outline-variant: '#c4c6cf'
  surface-tint: '#485f83'
  primary: '#001835'
  on-primary: '#ffffff'
  primary-container: '#142d4e'
  on-primary-container: '#7e95bc'
  inverse-primary: '#b0c8f1'
  secondary: '#27609e'
  on-secondary: '#ffffff'
  secondary-container: '#8abbff'
  on-secondary-container: '#004a87'
  tertiary: '#001a28'
  on-tertiary: '#ffffff'
  tertiary-container: '#003046'
  on-tertiary-container: '#5e9ac0'
  error: '#ba1a1a'
  on-error: '#ffffff'
  error-container: '#ffdad6'
  on-error-container: '#93000a'
  primary-fixed: '#d5e3ff'
  primary-fixed-dim: '#b0c8f1'
  on-primary-fixed: '#001b3b'
  on-primary-fixed-variant: '#30476a'
  secondary-fixed: '#d3e3ff'
  secondary-fixed-dim: '#a3c9ff'
  on-secondary-fixed: '#001c39'
  on-secondary-fixed-variant: '#004883'
  tertiary-fixed: '#c7e7ff'
  tertiary-fixed-dim: '#92cef6'
  on-tertiary-fixed: '#001e2e'
  on-tertiary-fixed-variant: '#004c6c'
  background: '#f7f9fb'
  on-background: '#191c1e'
  surface-variant: '#e0e3e5'
typography:
  display:
    fontFamily: Geist
    fontSize: 40px
    fontWeight: '600'
    lineHeight: 48px
    letterSpacing: -0.02em
  display-mobile:
    fontFamily: Geist
    fontSize: 30px
    fontWeight: '600'
    lineHeight: 36px
    letterSpacing: -0.015em
  headline-lg:
    fontFamily: Geist
    fontSize: 28px
    fontWeight: '600'
    lineHeight: 36px
    letterSpacing: -0.015em
  headline-lg-mobile:
    fontFamily: Geist
    fontSize: 22px
    fontWeight: '600'
    lineHeight: 28px
    letterSpacing: -0.01em
  headline-md:
    fontFamily: Geist
    fontSize: 20px
    fontWeight: '600'
    lineHeight: 26px
    letterSpacing: -0.01em
  headline-sm:
    fontFamily: Geist
    fontSize: 16px
    fontWeight: '600'
    lineHeight: 22px
    letterSpacing: -0.005em
  body-lg:
    fontFamily: Geist
    fontSize: 16px
    fontWeight: '400'
    lineHeight: 24px
    letterSpacing: 0em
  body-md:
    fontFamily: Geist
    fontSize: 14px
    fontWeight: '400'
    lineHeight: 20px
    letterSpacing: 0em
  body-sm:
    fontFamily: Geist
    fontSize: 12px
    fontWeight: '400'
    lineHeight: 18px
    letterSpacing: 0.005em
  label-md:
    fontFamily: JetBrains Mono
    fontSize: 13px
    fontWeight: '500'
    lineHeight: 16px
    letterSpacing: -0.01em
  label-sm:
    fontFamily: JetBrains Mono
    fontSize: 11px
    fontWeight: '500'
    lineHeight: 14px
    letterSpacing: 0.02em
  code-inline:
    fontFamily: JetBrains Mono
    fontSize: 13px
    fontWeight: '400'
    lineHeight: 18px
rounded:
  sm: 0.125rem
  DEFAULT: 0.25rem
  md: 0.375rem
  lg: 0.5rem
  xl: 0.75rem
  full: 9999px
spacing:
  gutter: 1rem
  gutter-desktop: 1.5rem
  margin: 1rem
  margin-tablet: 2rem
  margin-desktop: 3rem
  space-xs: 0.25rem
  space-sm: 0.5rem
  space-md: 1rem
  space-lg: 1.5rem
  space-xl: 2rem
---

## Brand & Style

This design system targets ambitious software engineers, technical candidates, and hiring managers seeking rigorous, structured career validation and AI-driven growth. The brand mood is disciplined, analytical, and authoritative—eschewing superficial AI novelty in favor of an ergonomic developer tool utility.

The aesthetic follows an ultra-clean, minimal, and structural design language reminiscent of precision enterprise developer IDEs and developer consoles:
- **Structural Integrity:** Heavy reliance on clear geometry, crisp 1px borders, and flat visual hierarchy.
- **No Novelty Distractions:** Zero decorative gradients, zero colored glows, and zero skeuomorphic skeuomorphism.
- **Data-Dense Clarity:** Information architecture prioritizes scannable text, structured code metrics, and low-cognitive-load layouts.

## Colors

The palette is strictly locked to an intentional blue-spectrum hierarchy, calibrated to prevent eye fatigue while guaranteeing AAA contrast compliance:

- **Deep Navy (`#142D4E`):** Serves as the primary brand ink, authoritative structural framing, primary typography, and terminal-grade emphasis.
- **Royal Blue (`#3269A8`):** Designated exclusively for primary action affordances, primary buttons, active tabs, and interactive states.
- **Ice Blue (`#8CC8F0`):** Utilized for delicate structural dividing lines, subtle 1px component borders, keyboard focus rings, and high-visibility selected outlines.
- **Pale Blue (`#E7F3FC`):** Applied to subtle background fills, code context blocks, interactive pill tags, and secondary button states.
- **Cloud White (`#F8FAFC`):** The foundational application background, table header contrast, and baseline panel surface. Pure white (`#FFFFFF`) is reserved exclusively for elevated card plates and active input fields to establish planar contrast against Cloud White.

## Typography

The typographic hierarchy prioritizes technical legibility, geometric precision, and scanning speed.

- **Primary & Interface Font (Geist):** Handles all marketing titles, operational headers, interface copy, and long-form advisory content. Its tight tracking, neutral apertures, and balanced x-height reinforce the developer-centric tone.
- **Technical & Utility Font (JetBrains Mono):** Reserved for technical tokens, career stage indicators, AI evaluation scores, skill tags, metadata stamps, and inline code snippets.
- **Weights & Hierarchy:** Limited strictly to regular (`400`), medium (`500`), and semi-bold (`600`) to maintain restraint. Text color defaults to Deep Navy (`#142D4E`), with secondary metadata muted to an opacity-derived tier (`rgba(20, 45, 78, 0.65)`).

## Layout & Spacing

The layout is constructed on a 4px/8px systematic modular rhythm anchored by a responsive fluid grid system:

- **Desktop (1024px+):** 12-column fluid grid, max-width bounded at 1280px to preserve code readability. Standard gutter is `1.5rem` (`24px`), with outer canvas padding at `3rem` (`48px`).
- **Tablet (640px - 1023px):** 8-column layout, gutters scaling to `1rem` (`16px`), outer margin at `2rem` (`32px`).
- **Mobile (< 640px):** Single-column stacked layout with full-bleed cards, `1rem` (`16px`) side margins, and vertical element spacing compressed to compact intervals.

Component internals use standard spacing tokens: micro-elements and chip internal padding leverage `space-xs` (4px) and `space-sm` (8px); form controls, list items, and standard cards leverage `space-md` (16px) and `space-lg` (24px); structural page divisions use `space-xl` (32px).

## Elevation & Depth

This design system deliberately eschews blurred drop shadows, multi-tiered ambient lighting, and glassmorphic blurs. Depth is achieved via **low-contrast structural outlines and planar surface shifts**:

- **Ground Plane (Base):** Cloud White (`#F8FAFC`).
- **Surface Tier (Cards & Panels):** Pure White (`#FFFFFF`) with a 1px solid border in Ice Blue (`#8CC8F0`).
- **Inset / Sub-tier:** Pale Blue (`#E7F3FC`) with no border, used for contextual analysis blocks, code evaluation sandboxes, and input backgrounds.
- **Interactive Focus & Hover:** Focus states are declared with a crisp `0 0 0 2px #8CC8F0` ring and a 1px solid outline in Royal Blue (`#3269A8`). Surfaces do not lift on the Z-axis on hover; they shift border tones or transition background fills subtly without simulated physics.

## Shapes

The design system embraces a **Soft (Level 1)** geometric aesthetic that preserves sharp, tool-like precision while removing aggressive edges:

- **Base Radius (`0.25rem` / `4px`):** Applied to buttons, input fields, checkboxes, dropdown menus, and standard interactive controls.
- **Large Radius (`0.5rem` / `8px`):** Applied to structural dashboard panels, analytics cards, career path containers, and modal dialogs.
- **Pill Radius (`9999px`):** Reserved exclusively for skill tags, metric chips, and AI verification badges to visually separate status metadata from operational rectangular components.

## Components

### Buttons
- **Primary:** Background Royal Blue (`#3269A8`), foreground `#FFFFFF`, font Geist Semi-Bold 14px, 4px border radius. Padding: 8px 16px. Hover state: `#275488`. Active state: `#1D3F66`. No drop shadow.
- **Secondary:** Background Pale Blue (`#E7F3FC`), foreground Royal Blue (`#3269A8`), 1px solid border in Ice Blue (`#8CC8F0`). Hover state: background shifts to Ice Blue (`#8CC8F0`) at 20% opacity.
- **Tertiary / Ghost:** Transparent background, foreground Deep Navy (`#142D4E`), hover state uses Pale Blue (`#E7F3FC`).

### Input Fields & Controls
- **Inputs:** Pure White background, 1px solid Ice Blue (`#8CC8F0`) border, text Deep Navy (`#142D4E`), font Geist 14px. Focus state: 1px solid Royal Blue (`#3269A8`) paired with an external 2px Ice Blue (`#8CC8F0`) focus ring.
- **Checkboxes & Radios:** 16px square/circle with 1px solid Ice Blue (`#8CC8F0`) border. When checked, background fills with Royal Blue (`#3269A8`) displaying a white icon.

### Chips & Pill Tags
- **Skill / Metric Tags:** Background Pale Blue (`#E7F3FC`), text Deep Navy (`#142D4E`), font JetBrains Mono 11px, border 1px solid Ice Blue (`#8CC8F0`), fully rounded (`rounded-full`). Padding: 2px 8px.

### Cards & Evaluation Modules
- **Container:** Pure White (`#FFFFFF`) surface, 8px border radius, enclosed in a 1px solid Ice Blue (`#8CC8F0`) border. Header regions utilize a Pale Blue (`#E7F3FC`) bottom-divider line (1px) with padding set to `space-md` (16px).

### Lists & Career Roadmaps
- **Career Path Items:** Connected via a vertical 1px solid Ice Blue (`#8CC8F0`) hairline. Milestone nodes use an 8px circular indicator filled with Royal Blue (`#3269A8`). Alternating milestone blocks utilize Pale Blue (`#E7F3FC`) background tints to signify current, past, and projected career trajectories.