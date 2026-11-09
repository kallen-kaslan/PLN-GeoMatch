import logo from "@/assets/pln-logo.png";

// Original PLN mark: https://commons.wikimedia.org/wiki/File:Logo_PLN.png
export function PlnLogo({ className = "" }: { className?: string }) {
  return <img src={logo} alt="Logo PLN" width={2480} height={3397} draggable={false} className={`auth-pln-logo ${className}`} />;
}
