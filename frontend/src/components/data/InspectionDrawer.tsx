import { useEffect, useRef, type ReactNode } from "react";
import { createPortal } from "react-dom";

export function InspectionDrawer({ label, onClose, children }: { label: string; onClose: () => void; children: ReactNode }) {
  const dialog = useRef<HTMLDialogElement>(null);
  const pressedOutside = useRef(false);
  const isOutside = (element: HTMLDialogElement, x: number, y: number) => {
    const bounds = element.getBoundingClientRect();
    return x < bounds.left || x > bounds.right || y < bounds.top || y > bounds.bottom;
  };
  useEffect(() => {
    const previous = document.activeElement;
    const overflow = document.body.style.overflow;
    const element = dialog.current;
    document.body.style.overflow = "hidden";
    element?.showModal();
    return () => {
      element?.close();
      document.body.style.overflow = overflow;
      if (previous instanceof HTMLElement && previous.isConnected) previous.focus({ preventScroll: true });
    };
  }, []);
  return createPortal(<dialog ref={dialog} aria-label={label} className="geo-drawer neo-scrollbar backdrop:bg-black/50"
    onPointerDown={(event) => { pressedOutside.current = event.target === event.currentTarget && isOutside(event.currentTarget, event.clientX, event.clientY); }}
    onClick={(event) => {
      if (pressedOutside.current && event.target === event.currentTarget && isOutside(event.currentTarget, event.clientX, event.clientY)) onClose();
      pressedOutside.current = false;
    }}
    onCancel={(event) => { event.preventDefault(); onClose(); }}>{children}</dialog>, document.body);
}
