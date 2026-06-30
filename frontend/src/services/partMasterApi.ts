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
  standard_part: boolean;
  latest_version: string;
  status: 'WIP' | 'RELEASED' | 'OBSOLETE';
  checkout_user: string | null;
  is_assembly: boolean;
  child_count: number;
}

export interface PartRevisionBrief {
  version: string;
  status: string;
  iterations: { iteration: number; iteration_note?: string; check_in_date?: string | null }[];
}

export interface UsageLinkBrief {
  component_number: string;
  component_name: string;
  amount: number;
  unit: string;
}

export interface PartMasterDetail extends PartMasterListItem {
  revisions: PartRevisionBrief[];
  usage_links: UsageLinkBrief[];
}

export const partMasterApi = {
  list: (params?: { search?: string }) => api.get('/parts', { params: wsParams(params) }),
  get: (number: string) => api.get(`/parts/${encodeURIComponent(number)}`, { params: wsParams() }),
};
