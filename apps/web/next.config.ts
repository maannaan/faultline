import path from "node:path";
import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  outputFileTracingRoot: path.resolve(process.cwd()),
  allowedDevOrigins: ["127.0.0.1"],
};

export default nextConfig;
