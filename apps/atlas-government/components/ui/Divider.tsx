export function Divider({ label }: { label?: string }) { return label ? <div className="dsDivider labeled" role="separator"><span>{label}</span></div> : <hr className="dsDivider" />; }
