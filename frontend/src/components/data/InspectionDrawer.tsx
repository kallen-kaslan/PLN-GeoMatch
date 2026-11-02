import { useEffect, useRef, type ReactNode } from "react";
import { createPortal } from "react-dom";

export function InspectionDrawer({ label, onClose, children }: { label: string; onClose: () => void; children: ReactNode }) {
  const dialog = useRef<HTMLDialogElement>(null);
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
  return createPortal(<dialog ref={dialog} aria-label={label} className="geo-drawer neo-scrollbar" onCancel={(event) => { event.preventDefault(); onClose(); }}>{children}</dialog>, document.body);
}
