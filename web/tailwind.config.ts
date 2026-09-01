import type { Config } from "tailwindcss";

const config: Config = {
  content: [
    "./pages/**/*.{js,ts,jsx,tsx,mdx}",
    "./components/**/*.{js,ts,jsx,tsx,mdx}",
    "./app/**/*.{js,ts,jsx,tsx,mdx}",
  ],
  theme: {
    extend: {
      colors: {
        // Section 2: Color System Tokens
        ink: {
          900: "#12203B", // Primary brand ink — navigation, headers, primary buttons
          600: "#3C4E70", // Secondary text, inactive nav states
        },
        paper: {
          100: "#F1F3F1", // App/dashboard background (cool grey-green off-white)
          "000": "#FFFFFF", // Card surfaces, elevated panels
        },
        brass: {
          500: "#A6742C", // Signature accent — seal badge, ruler ticks, signature CTA
        },
        verdict: {
          pass: "#1E7A4D", // PASS seal badge, success states
          fail: "#B3261E", // FAIL seal badge, error states
          pending: "#B5730B", // PENDING REVIEW seal badge, warning states
          neutral: "#6B7280", // CALIBRATION FAILED / unknown states
        },
      },
      fontFamily: {
        // Section 3: Typography System
        display: ["var(--font-space-grotesk)", "Space Grotesk", "sans-serif"],
        body: ["var(--font-inter)", "Inter", "sans-serif"],
        mono: ["var(--font-ibm-plex-mono)", "IBM Plex Mono", "monospace"],
      },
      fontSize: {
        // Section 3: Type scale (base 16px, 1.25 ratio: 12 / 16 / 20 / 25 / 31 / 39 / 49px)
        xs: ["12px", { lineHeight: "16px", letterSpacing: "0.02em" }],
        base: ["16px", { lineHeight: "24px" }],
        lg: ["20px", { lineHeight: "28px" }],
        xl: ["25px", { lineHeight: "32px" }],
        "2xl": ["31px", { lineHeight: "38px" }],
        "3xl": ["39px", { lineHeight: "46px" }],
        "4xl": ["49px", { lineHeight: "56px" }],
      },
      spacing: {
        // Section 4: 8px Base Spacing Grid
        "0.5": "4px",
        "1": "8px",
        "2": "16px",
        "3": "24px",
        "4": "32px",
        "5": "40px",
        "6": "48px", // 48px minimum touch target height
        "8": "64px",
        "10": "80px",
        "12": "96px",
      },
      maxWidth: {
        desktop: "1440px", // §4 Web grid max content width
        form: "720px",    // §4 Forms and detail panels max width
      },
      minHeight: {
        touch: "48px",   // §4 Minimum touch target height
      },
      borderRadius: {
        card: "4px",     // §5.3 Small radius — official documentation feel
      },
    },
  },
  plugins: [],
};

export default config;
