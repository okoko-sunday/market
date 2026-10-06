import type { NextConfig } from "next";
// `build` runs strict `tsc --noEmit` first. This bypasses a Next 16.3.8
// showConfig parser regression while preserving a mandatory type gate.
const nextConfig:NextConfig={typescript:{ignoreBuildErrors:true},images:{remotePatterns:[{protocol:"https",hostname:"**"},{protocol:"http",hostname:"localhost"}]}};
export default nextConfig;
