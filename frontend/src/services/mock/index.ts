import api from '../api';
import { mockAdapter } from './adapter';

/** 在 mock 模式下，把 axios 默认 adapter 换成本地 mock 适配层。 */
export function installMock(): void {
  api.defaults.adapter = mockAdapter;
  console.info('[mock] 已启用前端 mock 适配层（VITE_USE_MOCK=1）');
}
