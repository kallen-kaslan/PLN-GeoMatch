import { useEffect, useState } from "react";

export function useDebouncedSearch(value: string, delay = 350): string {
  const [settled, setSettled] = useState(value);
  useEffect(() => {
    const timer = window.setTimeout(() => setSettled(value), delay);
    return () => window.clearTimeout(timer);
  }, [value, delay]);
  return value ? settled : "";
}
