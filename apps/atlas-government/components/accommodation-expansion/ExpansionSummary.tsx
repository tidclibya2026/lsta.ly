export function ExpansionSummary({data}:{data:Record<string,unknown>}){return <dl>{Object.entries(data).map(([k,v])=><div key={k}><dt>{k}</dt><dd>{String(v)}</dd></div>)}</dl>}
