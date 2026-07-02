import axios from 'axios';
import { useAuthStore } from '../stores/auth';

export const inventoryAxios = axios.create({ baseURL: '/api/inventory', timeout: 30000 });
inventoryAxios.interceptors.request.use((config) => {
  const token = useAuthStore.getState().token;
  if (token) config.headers.Authorization = `Bearer ${token}`;
  return config;
});

export const inventoryApi = {
  // 仓库
  listWarehouses: () => inventoryAxios.get('/warehouses'),
  createWarehouse: (data: any) => inventoryAxios.post('/warehouses', data),
  updateWarehouse: (id: string, data: any) => inventoryAxios.put(`/warehouses/${id}`, data),
  deleteWarehouse: (id: string) => inventoryAxios.delete(`/warehouses/${id}`),
  // 物料
  listMaterials: (params?: { search?: string; source_type?: string; track_mode?: string }) =>
    inventoryAxios.get('/materials', { params }),
  createMaterial: (data: any) => inventoryAxios.post('/materials', data),
  enableFromPdm: (data: any) => inventoryAxios.post('/materials/enable-from-pdm', data),
  updateMaterial: (id: string, data: any) => inventoryAxios.put(`/materials/${id}`, data),
  deleteMaterial: (id: string) => inventoryAxios.delete(`/materials/${id}`),
  // 库存
  listStock: (params?: { material?: string; warehouse_id?: string; low_only?: boolean }) =>
    inventoryAxios.get('/stock', { params }),
  listLedger: (params?: { material_id?: string; warehouse_id?: string; doc_id?: string }) =>
    inventoryAxios.get('/stock/ledger', { params }),
  // 单据
  listDocuments: (params?: { page?: number; page_size?: number; doc_type?: string; status?: string; search?: string }) =>
    inventoryAxios.get('/documents', { params }),
  getDocument: (id: string) => inventoryAxios.get(`/documents/${id}`),
  createDocument: (data: any) => inventoryAxios.post('/documents', data),
  updateDocument: (id: string, data: any) => inventoryAxios.put(`/documents/${id}`, data),
  deleteDocument: (id: string) => inventoryAxios.delete(`/documents/${id}`),
  submit: (id: string) => inventoryAxios.post(`/documents/${id}/submit`),
  withdraw: (id: string) => inventoryAxios.post(`/documents/${id}/withdraw`),
  review: (id: string, data: { decision: string; comment?: string }) => inventoryAxios.post(`/documents/${id}/review`, data),
  assignKeeper: (id: string, keeperId: string) => inventoryAxios.post(`/documents/${id}/assign-keeper`, { keeper_id: keeperId }),
  post: (id: string, data?: { counts?: { line_id: string; counted_quantity: number }[] }) =>
    inventoryAxios.post(`/documents/${id}/post`, data || {}),
  cancel: (id: string) => inventoryAxios.post(`/documents/${id}/cancel`),
};
