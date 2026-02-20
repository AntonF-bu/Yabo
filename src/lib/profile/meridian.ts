/* ------------------------------------------------------------------ */
/*  Meridian — single source of truth for all Dossier design tokens    */
/* ------------------------------------------------------------------ */

export const M = {
  // Colors
  ink: '#1A1715',
  inkSecondary: '#6B6560',
  inkTertiary: '#8A8580',
  inkGhost: '#A09A94',
  gold: '#9A7B5B',
  goldLight: 'rgba(154, 123, 91, 0.06)',
  bg: '#FAF8F4',
  surface: '#F5F2EC',
  surfaceDeep: '#EEEAE3',
  border: '#E8E4DE',
  white: '#FFFFFF',
  profit: '#4A7C59',
  loss: '#A84B3F',
  warning: '#C4873B',
  info: '#5B7B9A',

  // Fonts
  serif: "'Newsreader', Georgia, serif",
  sans: "'Inter', system-ui, sans-serif",
  mono: "'IBM Plex Mono', monospace",

  // Radii
  card: 14,
  cardLg: 16,

  // Severity colors (for blind spots, risk)
  severityColor: (severity: string) => {
    switch (severity) {
      case 'danger': return '#A84B3F'
      case 'warning': return '#C4873B'
      case 'info': return '#5B7B9A'
      case 'opportunity': return '#4A7C59'
      case 'high': return '#A84B3F'
      case 'medium': return '#C4873B'
      case 'moderate': return '#C4873B'
      case 'low': return '#4A7C59'
      default: return '#8A8580'
    }
  },
} as const
