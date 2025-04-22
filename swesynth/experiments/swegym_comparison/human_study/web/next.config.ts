import { NextConfig } from 'next';

const nextConfig: NextConfig = {
  typescript: {
    ignoreBuildErrors: true, // Ignore TypeScript errors
  },
  eslint: {
    ignoreDuringBuilds: true, // Ignore ESLint errors
  },
};

export default nextConfig;
