import type { AxiosAdapter, AxiosResponse, InternalAxiosRequestConfig } from 'axios';
import { AxiosError } from 'axios';
import { routes } from './routes';

const DELAY = 100; // 模拟网络延迟（ms）

function parseBody(data: unknown): any {
  if (data == null) return undefined;
  if (typeof data === 'string') {
    try {
      return JSON.parse(data);
    } catch {
      return data;
    }
  }
  return data;
}

/** 前端 mock 适配器：按 method + url 路由到 fixtures，未命中返回 501 并 warn。 */
export const mockAdapter: AxiosAdapter = async (
  config: InternalAxiosRequestConfig,
): Promise<AxiosResponse> => {
  const method = (config.method || 'get').toLowerCase();
  const fullUrl = config.url || '';
  const [path, qs] = fullUrl.split('?');

  for (const r of routes) {
    if (r.method !== method) continue;
    const m = r.pattern.exec(path);
    if (!m) continue;
    const params: Record<string, string> = {};
    (r.keys || []).forEach((k, i) => {
      params[k] = m[i + 1];
    });
    const data = await r.handler({
      config,
      params,
      body: parseBody(config.data),
      query: new URLSearchParams(qs || ''),
    });
    await new Promise((res) => setTimeout(res, DELAY));
    return { data, status: 200, statusText: 'OK', headers: {}, config, request: {} };
  }

  console.warn(`[mock] 未实现的接口: ${method.toUpperCase()} ${path}`);
  await new Promise((res) => setTimeout(res, DELAY));
  return Promise.reject(
    new AxiosError(`mock 未实现: ${method} ${path}`, '501', config, null, {
      data: { detail: 'mock not implemented' },
      status: 501,
      statusText: 'Not Implemented',
      headers: {},
      config,
      request: {},
    } as AxiosResponse),
  );
};
