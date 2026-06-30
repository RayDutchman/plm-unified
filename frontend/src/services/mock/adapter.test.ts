import { describe, it, expect, vi } from 'vitest';
import { mockAdapter } from './adapter';
import type { InternalAxiosRequestConfig } from 'axios';

function cfg(method: string, url: string, data?: any): InternalAxiosRequestConfig {
  return { method, url, data, headers: {} as any } as InternalAxiosRequestConfig;
}

describe('mockAdapter', () => {
  it('命中路由返回 fixture（status 200）', async () => {
    const resp = await mockAdapter(cfg('post', '/auth/token'));
    expect(resp.status).toBe(200);
    expect(resp.data.access_token).toBeTruthy();
  });

  it('解析 path 参数（GET /dashboard/folders/:id/shares）', async () => {
    const resp = await mockAdapter(cfg('get', '/dashboard/folders/abc/shares'));
    expect(resp.status).toBe(200);
    expect(Array.isArray(resp.data)).toBe(true);
  });

  it('未命中接口 → 501 reject 且 warn', async () => {
    const warn = vi.spyOn(console, 'warn').mockImplementation(() => {});
    await expect(mockAdapter(cfg('get', '/nope/123'))).rejects.toMatchObject({ code: '501' });
    expect(warn).toHaveBeenCalled();
    warn.mockRestore();
  });
});
