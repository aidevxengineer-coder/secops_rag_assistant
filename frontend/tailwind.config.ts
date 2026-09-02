import type { Config } from "tailwindcss";
import typography from "@tailwindcss/typography";

const config: Config = {
  content: ["./app/**/*.{ts,tsx}", "./components/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        base: "#12151B",
        surface: "#1A1F28",
        elevated: "#232935",
        hairline: "#2A3140",
        accent: { DEFAULT: "#E8A33D", dim: "#8A6427" },
        verified: "#4FA87C",
        text: { primary: "#E4E7EC", muted: "#8B93A1" },
      },
      fontFamily: {
        mono: ["var(--font-plex-mono)", "monospace"],
        sans: ["var(--font-inter)", "sans-serif"],
      },
      boxShadow: {
        "accent-glow": "0 0 0 1px rgba(232, 163, 61, 0.4), 0 0 18px rgba(232, 163, 61, 0.15)",
        panel: "-8px 0 24px rgba(0, 0, 0, 0.25)",
      },
      typography: ({ theme }: { theme: (path: string) => string }) => ({
        invert: {
          css: {
            "--tw-prose-body": theme("colors.text.primary"),
            "--tw-prose-headings": theme("colors.text.primary"),
            "--tw-prose-bold": theme("colors.text.primary"),
            "--tw-prose-links": theme("colors.accent.DEFAULT"),
            "--tw-prose-code": theme("colors.accent.DEFAULT"),
            "--tw-prose-quotes": theme("colors.text.muted"),
            "--tw-prose-bullets": theme("colors.text.muted"),
            "--tw-prose-hr": theme("colors.hairline"),
            "--tw-prose-th-borders": theme("colors.hairline"),
            "--tw-prose-td-borders": theme("colors.hairline"),
            maxWidth: "none", // prose defaults to 65ch, which fights your own max-w-[75%] on the bubble
          },
        },
      }),
    },
  },
  plugins: [typography],
};

export default config;