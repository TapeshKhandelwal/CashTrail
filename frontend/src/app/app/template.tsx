import type { ReactNode } from "react";

/** Re-mounts on every navigation inside /app, so each page's content rises 8px as it arrives. */
export default function AppTemplate({ children }: { children: ReactNode }) {
  return <div className="page-enter">{children}</div>;
}
