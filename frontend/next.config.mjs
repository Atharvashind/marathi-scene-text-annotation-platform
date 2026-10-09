/** @type {import('next').NextConfig} */
const nextConfig = {
  output: 'standalone',

  // Prevent react-konva / konva from being bundled on the server
  webpack: (config, { isServer }) => {
    if (isServer) {
      config.externals = [
        ...(config.externals || []),
        'canvas',
        'konva',
        'react-konva',
      ];
    }
    return config;
  },

  async rewrites() {
    const apiBase = process.env.NEXT_PUBLIC_API_BASE_URL || 'http://localhost:8000';
    return [
      {
        source: '/api/images/file/:path*',
        destination: `${apiBase}/api/images/file/:path*`,
      },
    ];
  },
};

export default nextConfig;
