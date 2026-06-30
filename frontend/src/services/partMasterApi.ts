import api from './api';
import { useAuthStore } from '../stores/auth';

function wsParams(params?: Record<string, unknown>): Record<string, unknown> {
  const user = useAuthStore.getState().user;
  return { ...params, workspace_id: user?.workspaceId || '00000000-0000-0000-0000-000000000001' };
}

/** 零部件（统一 PartMaster 模型：零件与装配体不分家，装配体=有子件的 PartMaster）。 */
export interface PartMasterListItem {
  id: string;
  number: string;
  name: string;
  type: string;
  standardPart: boolean;
  latestVersion: string;
  latestStatus: 'WIP' | 'FROZEN' | 'RELEASED' | 'OBSOLETE';
  checkoutUserId: string | null;
  isAssembly: boolean;
  childCount: number;
}

export interface PartRevisionBrief {
  version: string;
  status: string;
  iterations: { iteration: number; iterationNote?: string; checkInDate?: string | null }[];
}

export interface UsageLinkBrief {
  componentNumber: string;
  componentName: string;
  amount: number;
  unit: string;
}

export interface PartMasterDetail extends PartMasterListItem {
  revisions: PartRevisionBrief[];
  usageLinks: UsageLinkBrief[];
}

export const partMasterApi = {
  list: (params?: { search?: string }) => api.get('/parts', { params: wsParams(params) }),
  get: (number: string) => api.get(`/parts/${encodeURIComponent(number)}`, { params: wsParams() }),
  create: (data: { number: string; name: string; type?: string; standard_part?: boolean; description?: string }) => api.post('/parts', { ...data, workspace_id: useAuthStore.getState().user?.workspaceId || '00000000-0000-0000-0000-000000000001' }),
  update: (id: string, data: { name?: string; type?: string; standard_part?: boolean }) => api.put(`/parts/${encodeURIComponent(id)}`, data, { params: wsParams() }),
  delete: (id: string) => api.delete(`/parts/${encodeURIComponent(id)}`, { params: wsParams() }),
};
