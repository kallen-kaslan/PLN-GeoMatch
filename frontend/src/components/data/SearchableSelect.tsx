import { useEffect, useId, useLayoutEffect, useRef, useState, type KeyboardEvent } from "react";
import { createPortal } from "react-dom";
import { Check, ChevronDown } from "lucide-react";

type Option = { value: string; label: string };
type MenuPosition = { left: number; top: number; width: number; maxHeight: number; above: boolean };

export function SearchableSelect({ label, value, options, onChange, disabled = false, placeholder = "Pilih atau ketik untuk mencari...", emptyText = "Tidak ada pilihan sesuai pencarian." }: {
  label: string; value: string; options: Option[]; onChange: (value: string) => void;
  disabled?: boolean; placeholder?: string; emptyText?: string;
}) {
  const id = useId();
  const root = useRef<HTMLDivElement>(null);
  const anchor = useRef<HTMLDivElement>(null);
  const input = useRef<HTMLInputElement>(null);
  const list = useRef<HTMLUListElement>(null);
  const [open, setOpen] = useState(false);
  const [query, setQuery] = useState<string | null>(null);
  const [active, setActive] = useState(0);
  const [position, setPosition] = useState<MenuPosition | null>(null);
  const shown = options.filter((item) => item.label.toLocaleLowerCase().includes((query ?? "").toLocaleLowerCase()));
  const selected = options.find((item) => item.value === value);
  const expanded = open && !disabled;
  const activeIndex = Math.min(active, shown.length - 1);
  const close = () => { setOpen(false); setQuery(null); };
  const reveal = () => { setActive(Math.max(0, options.findIndex((item) => item.value === value))); setOpen(true); };
  const choose = (option: Option) => { onChange(option.value); close(); setActive(0); };

  useLayoutEffect(() => {
    if (!expanded) return;
    const measure = () => {
      const rect = anchor.current?.getBoundingClientRect();
      if (!rect) return;
      const viewport = window.visualViewport;
      const edgeLeft = (viewport?.offsetLeft ?? 0) + 8;
      const edgeTop = (viewport?.offsetTop ?? 0) + 8;
      const edgeRight = (viewport?.offsetLeft ?? 0) + (viewport?.width ?? window.innerWidth) - 8;
      const edgeBottom = (viewport?.offsetTop ?? 0) + (viewport?.height ?? window.innerHeight) - 8;
      if (rect.bottom <= edgeTop || rect.top >= edgeBottom) { setOpen(false); setQuery(null); return; }
      const below = Math.max(0, edgeBottom - rect.bottom - 6);
      const aboveSpace = Math.max(0, rect.top - edgeTop - 6);
      const above = below < Math.min(240, aboveSpace);
      const width = Math.min(rect.width, edgeRight - edgeLeft);
      const next = { left: Math.max(edgeLeft, Math.min(rect.left, edgeRight - width)), top: above ? rect.top - 6 : rect.bottom + 6, width, maxHeight: Math.min(288, above ? aboveSpace : below), above };
      setPosition((previous) => previous && Object.keys(next).every((key) => previous[key as keyof MenuPosition] === next[key as keyof MenuPosition]) ? previous : next);
    };
    measure();
    const observer = new ResizeObserver(measure);
    if (anchor.current) observer.observe(anchor.current);
    window.addEventListener("resize", measure);
    window.addEventListener("scroll", measure, true);
    window.visualViewport?.addEventListener("resize", measure);
    window.visualViewport?.addEventListener("scroll", measure);
    return () => {
      observer.disconnect();
      window.removeEventListener("resize", measure);
      window.removeEventListener("scroll", measure, true);
      window.visualViewport?.removeEventListener("resize", measure);
      window.visualViewport?.removeEventListener("scroll", measure);
    };
  }, [expanded]);

  useLayoutEffect(() => {
    const menu = list.current;
    const option = menu?.querySelector<HTMLElement>('[data-active="true"]');
    if (!menu || !option) return;
    // Scroll only the list, never the surrounding page/card.
    if (option.offsetTop < menu.scrollTop) menu.scrollTop = option.offsetTop;
    else if (option.offsetTop + option.offsetHeight > menu.scrollTop + menu.clientHeight) menu.scrollTop = option.offsetTop + option.offsetHeight - menu.clientHeight;
  }, [activeIndex, expanded, position, shown.length]);

  useEffect(() => {
    if (!expanded) return;
    const outside = (event: PointerEvent) => {
      const target = event.target as Node;
      if (!root.current?.contains(target) && !list.current?.contains(target)) { setOpen(false); setQuery(null); }
    };
    document.addEventListener("pointerdown", outside);
    return () => document.removeEventListener("pointerdown", outside);
  }, [expanded]);

  const keys = (event: KeyboardEvent<HTMLInputElement>) => {
    if (event.key === "ArrowDown" || event.key === "ArrowUp") {
      event.preventDefault(); setOpen(true);
      setActive(!expanded ? event.key === "ArrowDown" ? 0 : Math.max(0, shown.length - 1) : Math.max(0, Math.min(shown.length - 1, activeIndex + (event.key === "ArrowDown" ? 1 : -1))));
    } else if (expanded && query === null && (event.key === "Home" || event.key === "End")) {
      event.preventDefault(); setActive(event.key === "Home" ? 0 : Math.max(0, shown.length - 1));
    } else if (event.key === "Enter") {
      event.preventDefault();
      if (expanded && shown[activeIndex]) choose(shown[activeIndex]); else reveal();
    } else if (event.key === "Escape") {
      if (expanded) { event.preventDefault(); event.stopPropagation(); }
      close();
    }
  };

  return <div ref={root} className="min-w-0 space-y-2" onBlur={(event) => { if (!event.currentTarget.contains(event.relatedTarget) && !list.current?.contains(event.relatedTarget)) close(); }}>
    <label htmlFor={id} className="block text-sm font-semibold">{label}</label>
    <div ref={anchor} className="relative">
      <input ref={input} id={id} role="combobox" aria-autocomplete="list" aria-expanded={expanded} aria-controls={expanded && position ? `${id}-list` : undefined} aria-activedescendant={expanded && position && shown[activeIndex] ? `${id}-option-${activeIndex}` : undefined} autoComplete="off" disabled={disabled} title={selected?.label} value={query ?? selected?.label ?? ""} placeholder={placeholder} onFocus={reveal} onClick={() => { if (!expanded) reveal(); }} onKeyDown={keys} onChange={(event) => { setQuery(event.target.value); setActive(0); setOpen(true); if (value) onChange(""); }} className="min-h-11 w-full rounded-md border border-ui-border bg-white py-2.5 pr-12 pl-3 text-sm text-neo-black placeholder:text-slate-400 focus:border-ui-primary focus:outline-none focus:ring-1 focus:ring-ui-primary disabled:cursor-not-allowed disabled:bg-slate-50 disabled:opacity-60" />
      <button type="button" tabIndex={-1} disabled={disabled} aria-label={`Buka pilihan ${label}`} onMouseDown={(event) => event.preventDefault()} onClick={() => { input.current?.focus(); if (expanded) close(); else reveal(); }} className="absolute inset-y-0 right-2 flex w-8 items-center justify-center text-ui-muted disabled:opacity-50"><ChevronDown aria-hidden="true" size={16} className={expanded ? "rotate-180" : ""} /></button>
    </div>
    {expanded && position && createPortal(<ul ref={list} id={`${id}-list`} role="listbox" aria-label={label} style={{ position: "fixed", left: position.left, top: position.top, width: position.width, maxHeight: position.maxHeight, transform: position.above ? "translateY(-100%)" : undefined }} className="z-[1100] m-0 overflow-y-auto overscroll-contain rounded-lg border border-ui-border bg-white p-1 shadow-[0_8px_28px_rgba(28,41,70,0.16)]">
      {shown.length ? shown.map((item, index) => <li key={item.value} id={`${id}-option-${index}`} role="option" aria-selected={item.value === value} data-active={index === activeIndex} onMouseDown={(event) => event.preventDefault()} onMouseEnter={() => setActive(index)} onClick={() => choose(item)} className={`flex min-h-11 cursor-pointer items-start gap-3 rounded-md px-3 py-2.5 text-sm ${index === activeIndex ? "bg-ui-context text-ui-primary-text" : "text-neo-black hover:bg-slate-50"}`}><span className="min-w-0 flex-1 whitespace-normal [overflow-wrap:anywhere]">{item.label}</span>{item.value === value && <Check aria-hidden="true" size={16} className="mt-0.5 shrink-0 text-ui-primary" />}</li>) : <li role="presentation" className="px-3 py-3 text-sm text-ui-muted">{emptyText}</li>}
    </ul>, document.body)}
  </div>;
}
