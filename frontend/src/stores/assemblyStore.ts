/**
 * assemblyStore.ts
 *
 * 装配体查看器的全局状态管理。
 * 维护实例列表（来自 instances API）、
 * 每个实例的 GLB ArrayBuffer（由 LODController/GeometryWorker 填充）、
 * 以及相机/交互状态。
 */

import { create } from 'zustand';

/** instances API 返回的单个实例（camelCase） */
export interface AssemblyInstance {
  id: string;
  partNumber: string;
  version: string;
  iteration: number;
  /** 列优先 16 元素 4x4 变换矩阵（Three.js Matrix4.fromArray 兼容） */
  matrix: number[];
  xMin: number;
  yMin: number;
  zMin: number;
  xMax: number;
  yMax: number;
  zMax: number;
  /** vault 相对路径，如 default/parts/.../geometries/{uuid}.glb */
  geometryFullName?: string | null;

  // --- 运行时字段（不来自 API） ---
  /** 当前已加载的 geometry URL（用于 LODController 判断是否重复加载） */
  loadedUrl?: string;
  /** 是否加载出错 */
  loadError?: string;
}

export interface AssemblyState {
  // 数据
  instances: AssemblyInstance[];
  workspaceId: string;
  /** url → ArrayBuffer（已解析的 GLB 二进制，由 LODController 写入） */
  bufferCache: Map<string, ArrayBuffer>;
  /** url → 错误信息 */
  errorCache: Map<string, string>;

  // 加载状态
  loading: boolean;
  error: string | null;

  // 选中
  selectedId: string | null;

  // 显示选项
  showEdges: boolean;

  // Actions
  setWorkspaceId: (id: string) => void;
  loadInstances: (partNumber: string, version: string, token: string) => Promise<void>;
  setInstanceBuffer: (url: string, buffer: ArrayBuffer) => void;
  setInstanceError: (url: string, message: string) => void;
  selectInstance: (id: string | null) => void;
  toggleEdges: () => void;
  reset: () => void;
}

const initialState = {
  instances: [] as AssemblyInstance[],
  workspaceId: '00000000-0000-0000-0000-000000000001',
  bufferCache: new Map<string, ArrayBuffer>(),
  errorCache: new Map<string, string>(),
  loading: false,
  error: null as string | null,
  selectedId: null as string | null,
  showEdges: true,
};

export const useAssemblyStore = create<AssemblyState>((set, get) => ({
  ...initialState,

  setWorkspaceId: (id) => set({ workspaceId: id }),

  /**
   * 从后端 instances API 拉取实例列表。
   * GET /api/parts/{partNumber}/{version}/instances?workspace_id=...
   */
  loadInstances: async (partNumber, version, token) => {
    const { workspaceId } = get();
    set({ loading: true, error: null, instances: [] });
    try {
      const resp = await fetch(
        `/api/parts/${encodeURIComponent(partNumber)}/${encodeURIComponent(version)}/instances` +
          `?workspace_id=${encodeURIComponent(workspaceId)}`,
        {
          headers: {
            Authorization: `Bearer ${token}`,
            Accept: 'application/json',
          },
        },
      );
      if (!resp.ok) {
        const text = await resp.text();
        throw new Error(`HTTP ${resp.status}: ${text}`);
      }
      const data: AssemblyInstance[] = await resp.json();
      set({ instances: data, loading: false });
    } catch (err) {
      const msg = err instanceof Error ? err.message : String(err);
      set({ loading: false, error: msg });
    }
  },

  /**
   * LODController 调用：将 Worker 拉取到的 GLB buffer 存入缓存，
   * 同时更新对应实例的 loadedUrl。
   */
  setInstanceBuffer: (url, buffer) => {
    const { bufferCache, instances } = get();
    const newCache = new Map(bufferCache);
    newCache.set(url, buffer);

    // 更新所有 loadedUrl 与该 url 匹配的实例
    const newInstances = instances.map((inst) => {
      // 判断这个 url 是否是该实例的某个 quality 版本
      const instBase = buildBaseUrl(inst);
      if (url.startsWith(instBase)) {
        return { ...inst, loadedUrl: url, loadError: undefined };
      }
      return inst;
    });

    set({ bufferCache: newCache, instances: newInstances });
  },

  setInstanceError: (url, message) => {
    const { errorCache, instances } = get();
    const newCache = new Map(errorCache);
    newCache.set(url, message);

    const newInstances = instances.map((inst) => {
      const instBase = buildBaseUrl(inst);
      if (url.startsWith(instBase)) {
        return { ...inst, loadError: message };
      }
      return inst;
    });

    set({ errorCache: newCache, instances: newInstances });
  },

  selectInstance: (id) => set({ selectedId: id }),

  toggleEdges: () => set({ showEdges: !get().showEdges }),

  reset: () =>
    set({
      ...initialState,
      bufferCache: new Map(),
      errorCache: new Map(),
    }),
}));

/** 构建实例对应的 geometry endpoint base URL（不含 quality 参数） */
function buildBaseUrl(inst: AssemblyInstance): string {
  return (
    `/api/parts/${encodeURIComponent(inst.partNumber)}` +
    `/${encodeURIComponent(inst.version)}` +
    `/iterations/${inst.iteration}/geometry`
  );
}
