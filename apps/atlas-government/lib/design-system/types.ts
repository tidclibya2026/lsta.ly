import type { ComponentPropsWithoutRef, ElementType, ReactNode } from "react";
export type Tone = "neutral" | "info" | "success" | "warning" | "danger";
export type Size = "sm" | "md" | "lg";
export type InteractiveState = "default" | "hover" | "focus" | "disabled" | "loading" | "selected" | "error" | "success" | "warning";
export type PolymorphicProps<T extends ElementType> = { as?: T; children?: ReactNode } & Omit<ComponentPropsWithoutRef<T>, "as" | "children">;
