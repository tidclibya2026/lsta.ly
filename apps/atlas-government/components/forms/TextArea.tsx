import { useId, type TextareaHTMLAttributes } from "react";
export function TextArea({ label, ...props }: TextareaHTMLAttributes<HTMLTextAreaElement> & { label: string }) { const id = useId(); return <label className="dsField" htmlFor={id}><span>{label}</span><textarea id={id} {...props} /></label>; }
