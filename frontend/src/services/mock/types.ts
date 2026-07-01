import type { InternalAxiosRequestConfig } from 'axios';

export interface MockCtx {
  config: InternalAxiosRequestConfig;
  params: Record<string, string>;
  body: any;
  query: URLSearchParams;
}

export type MockHandler = (ctx: MockCtx) => any | Promise<any>;

export interface MockRoute {
  method: 'get' | 'post' | 'put' | 'delete' | 'patch';
  pattern: RegExp; // 匹配 config.url（去掉 baseURL 与 query）
  keys?: string[]; // 捕获组名 → params
  handler: MockHandler;
}
