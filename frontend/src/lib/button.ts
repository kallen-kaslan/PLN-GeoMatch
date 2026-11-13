const base = "touch-min gap-2 rounded-md border px-3 py-2 text-[13px] font-medium transition-colors focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-ui-primary disabled:cursor-not-allowed disabled:border-slate-200 disabled:bg-slate-100 disabled:text-slate-400 disabled:shadow-none";

export const buttonClass = {
  primary: `${base} geo-button-primary border-ui-primary bg-ui-primary text-white shadow-sm hover:bg-ui-primary-hover`,
  secondary: `${base} geo-button-secondary border-ui-border bg-white text-ui-primary-text hover:border-ui-primary/35 hover:bg-ui-context`,
  success: `${base} border-emerald-700 bg-emerald-700 text-white hover:bg-emerald-800`,
  warning: `${base} border-amber-200 bg-amber-50 text-amber-900 hover:bg-amber-100`,
  danger: `${base} border-red-200 bg-white text-red-700 hover:bg-red-50`,
} as const;
