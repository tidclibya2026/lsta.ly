import type { HTMLAttributes, ReactNode } from "react";
export function Card({ children, className = "", ...props }: HTMLAttributes<HTMLElement> & { children: ReactNode }) { return <article className={`dsCard ${className}`} {...props}>{children}</article>; }
