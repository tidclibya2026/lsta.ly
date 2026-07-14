export const designTokens = {
  colors: { governmentNavy: "#071c33", governmentNavySurface: "#0d2f52", governmentGold: "#d7a83c", white: "#ffffff", lightGray: "#eef2f6", successGreen: "#1e8e63", warningAmber: "#b97813", dangerRed: "#b54141", informationBlue: "#2674a8" },
  typography: { family: 'Arial,"Noto Kufi Arabic",sans-serif', sizes: { xs: 11, sm: 13, md: 15, lg: 18, xl: 27 }, weights: { regular: 400, medium: 600, bold: 700, extraBold: 800 } },
  spacing: { 1: 4, 2: 8, 3: 12, 4: 18, 5: 24, 6: 32 },
  radius: { sm: 6, md: 10, lg: 16, pill: 999 },
  shadows: { sm: "0 4px 14px #14223812", md: "0 7px 24px #14223818", overlay: "0 18px 50px #071c3340" },
  zIndex: { base: 1, dropdown: 20, overlay: 100, modal: 110, toast: 120 },
  breakpoints: { mobile: 520, tablet: 820, desktop: 1180 },
  transitions: { fast: "120ms ease", normal: "200ms ease", slow: "320ms ease" },
} as const;
