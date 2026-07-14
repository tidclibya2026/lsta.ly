import { useId, type SelectHTMLAttributes } from "react";
export interface SelectOption { value: string; label: string }
export function Select({ label, options, ...props }: SelectHTMLAttributes<HTMLSelectElement> & { label: string; options: SelectOption[] }) { const id = useId(); return <label className="dsField" htmlFor={id}><span>{label}</span><select id={id} {...props}>{options.map((option) => <option value={option.value} key={option.value}>{option.label}</option>)}</select></label>; }
