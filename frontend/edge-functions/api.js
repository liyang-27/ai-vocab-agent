// edge-functions/api.js
export default async function handleRequest(request, context) {
  const url = new URL(request.url);
  const path = url.pathname + url.search; // 保留路径和查询参数

  // 你的 ECS 公网 IP（或内网 IP，如果 EdgeOne 和 ECS 在同一区域可用内网）
  const backendHost = 'http://8.136.191.166:8000'; // 如果后端使用非 80 端口，加上端口，例如 http://8.136.191.166:3000
  const backendUrl = `${backendHost}${path}`;

  // 转发请求（保留方法、头、体）
  const backendResponse = await fetch(backendUrl, {
    method: request.method,
    headers: request.headers,
    body: request.body,
  });

  // 返回响应给客户端
  return backendResponse;
}