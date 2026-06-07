import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  // Pin the workspace root to this app (a stray lockfile in $HOME otherwise
  // makes Turbopack guess the wrong root).
  turbopack: { root: __dirname },
};

export default nextConfig;
