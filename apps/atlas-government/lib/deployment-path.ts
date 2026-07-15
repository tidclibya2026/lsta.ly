export function isStaticDemo(): boolean {
  return process.env.NEXT_PUBLIC_LSTA_DEPLOYMENT_MODE === "static-demo";
}

export function getBasePath(): string {
  return process.env.NEXT_PUBLIC_LSTA_BASE_PATH?.replace(/\/$/, "") || "";
}

export function withBasePath(path: string): string {
  if (/^(?:https?:|data:|blob:)/.test(path)) return path;
  const normalized = path.startsWith("/") ? path : `/${path}`;
  return `${getBasePath()}${normalized}`;
}
