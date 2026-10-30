const base = "touch-min gap-2 rounded-sm border-2 px-3 py-2 text-xs font-bold transition-[transform,colors,box-shadow] focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-neo-accent disabled:cursor-not-allowed disabled:border-gray-400 disabled:bg-gray-200 disabled:text-gray-600 disabled:shadow-none disabled:hover:bg-gray-200 active:translate-x-[1px] active:translate-y-[1px]";

// Each variant owns its colors so Tailwind never has to choose between two backgrounds.
export const buttonClass = {
  primary: `${base} border-neo-border bg-neo-black text-white shadow-[2px_2px_0_#4F86F7] hover:bg-neutral-800 hover:shadow-[1px_1px_0_#4F86F7] active:shadow-none`,
  secondary: `${base} border-neo-border bg-gray-100 text-neo-black shadow-[2px_2px_0_#0a0a0a] hover:bg-gray-200 hover:shadow-[1px_1px_0_#0a0a0a] active:shadow-none`,
  success: `${base} border-green-800 bg-green-700 text-white shadow-[2px_2px_0_#0a0a0a] hover:bg-green-800 hover:shadow-[1px_1px_0_#0a0a0a] active:shadow-none`,
  warning: `${base} border-amber-700 bg-amber-100 text-amber-950 shadow-[2px_2px_0_#0a0a0a] hover:bg-amber-200 hover:shadow-[1px_1px_0_#0a0a0a] active:shadow-none`,
  outline: `${base} border-neo-border bg-white text-neo-black shadow-[2px_2px_0_#0a0a0a] hover:bg-gray-50 hover:shadow-[1px_1px_0_#0a0a0a] active:shadow-none`,
  ghost: "touch-min gap-2 rounded-sm border border-transparent px-3 py-2 text-xs font-bold text-neo-black transition-colors hover:bg-gray-200/60 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-neo-accent disabled:opacity-50",
  danger: `${base} border-red-800 bg-red-600 text-white shadow-[2px_2px_0_#0a0a0a] hover:bg-red-700 hover:shadow-[1px_1px_0_#0a0a0a] active:shadow-none`,
} as const;
