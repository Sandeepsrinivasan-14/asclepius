const API = process.env.ASCLEPIUS_API_URL || "http://127.0.0.1:8000";

/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  compress: false,
  poweredByHeader: false,
  async rewrites() {
    return [
      { source: "/api/:path*", destination: `${API}/api/:path*` },
      { source: "/fhir/:path*", destination: `${API}/fhir/:path*` },
      { source: "/.well-known/smart-configuration", destination: `${API}/.well-known/smart-configuration` },
    ];
  },
};
export default nextConfig;
