import type { ReactNode } from "react";
import type { LucideIcon } from "lucide-react";

export function WorkspaceHeader({ icon: Icon, eyebrow, title, description, actions }: {
  icon: LucideIcon; eyebrow: string; title: ReactNode; description: string; actions?: ReactNode;
}) {
  return <header className="geo-workspace-heading">
    <div className="geo-workspace-heading-copy">
      <span className="geo-workspace-emblem" aria-hidden="true"><Icon size={25} /></span>
      <div className="min-w-0"><p className="geo-workspace-eyebrow">{eyebrow}</p><h1>{title}</h1><p className="geo-workspace-description">{description}</p></div>
    </div>
    {actions && <div className="geo-workspace-heading-actions">{actions}</div>}
    <Icon className="geo-workspace-watermark" aria-hidden="true" />
  </header>;
}

export function SectionHeading({ icon: Icon, title, description }: { icon: LucideIcon; title: string; description?: string }) {
  return <div className="geo-section-heading"><span aria-hidden="true"><Icon size={17} /></span><div className="min-w-0"><h2>{title}</h2>{description && <p>{description}</p>}</div></div>;
}
