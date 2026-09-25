const apiUrl = process.env.API_URL || "http://localhost:8000";

/** @type {import('next').NextConfig} */
const nextConfig = {
  output: "standalone",
  // Tarayıcıdan gelen /api istekleri arka uca yönlendirilir (yönetim paneli bunu kullanır)
  async rewrites() {
    return [{ source: "/api/:path*", destination: `${apiUrl}/api/:path*` }];
  },
};

export default nextConfig;
