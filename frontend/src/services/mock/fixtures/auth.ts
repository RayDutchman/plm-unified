import type { MockRoute } from '../types';

export const mockAdminUser = {
  id: '00000000-0000-0000-0000-000000000010',
  username: 'admin',
  real_name: '系统管理员',
  role: 'admin',
  department: '研发',
  phone: '',
  status: 'active',
  created_at: '2026-06-29T00:00:00Z',
  updated_at: '2026-06-29T00:00:00Z',
};

export const authRoutes: MockRoute[] = [
  {
    method: 'post',
    pattern: /^\/auth\/token$/,
    handler: () => ({
      access_token: 'mock-access-token',
      refresh_token: 'mock-refresh-token',
      token_type: 'bearer',
    }),
  },
  { method: 'get', pattern: /^\/auth\/me$/, handler: () => mockAdminUser },
  { method: 'post', pattern: /^\/auth\/change-password$/, handler: () => ({ message: '密码修改成功' }) },
];
