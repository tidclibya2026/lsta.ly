export function PilotProgressStepper(){return <ol aria-label="مراحل Pilot">{["Selection","Review","Dry Run","Authorization","Execution","Verification","Closure"].map(x=><li key={x}>{x}</li>)}</ol>}
