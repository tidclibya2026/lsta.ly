const isGitHubPages = process.env.GITHUB_ACTIONS === "true";

/** @type {import('next').NextConfig} */
const nextConfig = {
  output: "export",
  trailingSlash: true,
  images: { unoptimized: true },
  ...(isGitHubPages ? { basePath: "/lsta.ly", assetPrefix: "/lsta.ly/" } : {}),
};

export default nextConfig;
