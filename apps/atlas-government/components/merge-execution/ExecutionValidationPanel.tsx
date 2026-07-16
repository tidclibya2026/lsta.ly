export function ExecutionValidationPanel({value}:{value:Record<string,unknown>}){return <section><h2>نتائج التحقق</h2><pre>{JSON.stringify(value,null,2)}</pre></section>}
