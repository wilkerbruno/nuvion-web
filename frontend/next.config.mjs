/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  // Build mínimo (só o necessário pra rodar em produção) — usado pelo
  // Dockerfile deste projeto para uma imagem final bem menor. Ver
  // https://nextjs.org/docs/pages/api-reference/next-config-js/output
  output: "standalone",
};

export default nextConfig;
