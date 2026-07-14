import type { InputHTMLAttributes } from "react";
import { TextInput } from "./TextInput";
export function SearchInput(props: Omit<InputHTMLAttributes<HTMLInputElement>, "type"> & { label?: string }) { return <div className="dsSearch"><span aria-hidden="true">⌕</span><TextInput type="search" label={props.label ?? "بحث"} {...props} /></div>; }
