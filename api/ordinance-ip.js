// Vercel Serverless Function — 조례 API 서버 발신 IP 확인

export const config = { regions: ['icn1'] };

export default async function handler(req, res) {
  let ip = 'unknown';
  try {
    const resp = await fetch('https://api.ipify.org?format=json');
    const data = await resp.json();
    ip = data.ip;
  } catch (e) {
    ip = `error: ${e.message}`;
  }

  res.status(200).json({
    server_ip: ip,
    LAW_API_KEY_set: !!process.env.LAW_API_KEY,
    region: process.env.VERCEL_REGION || 'unknown',
  });
}
