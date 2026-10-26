const base = "touch-min gap-2 rounded-sm border-2 px-3 py-2 text-xs font-bold transition-colors focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-neo-accent disabled:cursor-not-allowed disabled:border-gray-400 disabled:bg-gray-200 disabled:text-gray-600 disabled:shadow-none disabled:hover:bg-gray-200";

// Each variant owns its colors so Tailwind never has to choose between two backgrounds.
export const buttonClass = {
  primary: `${base} border-neo-border bg-neo-black text-white shadow-[2px_2px_0_#ff6b35] hover:bg-neutral-800`,
  secondary: `${base} border-neo-border bg-gray-100 text-neo-black shadow-[2px_2px_0_#0a0a0a] hover:bg-gray-200`,
  success: `${base} border-green-800 bg-green-700 text-white shadow-[2px_2px_0_#0a0a0a] hover:bg-green-800`,
  warning: `${base} border-amber-700 bg-amber-100 text-amber-950 shadow-[2px_2px_0_#0a0a0a] hover:bg-amber-200`,
} as const;
