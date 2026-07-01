import { useState, useEffect, useMemo } from 'react';
import { useDataStore } from '../stores/data';
import { useAuthStore } from '../stores/auth';
import api, { assembliesApi, getWorkspaceId } from '../services/api';
import { bomApi } from '../services/api';
import { partMasterApi } from '../services/partMasterApi';
import { Modal } from './Modal';
import type { Part, Assembly } from '../types';

/* ----------------------------------------------------------------
   Types
   ---------------------------------------------------------------- */

interface CandidateItem {
  id: string;
  code: string;
  name: string;
  version: string;
  status: string;
  spec?: string;
  type: 'part' | 'component';
}

interface SelectedItem {
  id: string;
  code: string;
  name: string;
  version: string;
  status: string;
  type: 'part' | 'component';
  quantity: number;
}

interface AssemblyPartPickerProps {
  open: boolean;
  onClose: () => void;
  onConfirm: (items: { child_type: string; child_id: string; quantity: number }[]) => void;
  currentAssemblyId?: string;
  existingChildIds?: Set<string>;
}

/* ----------------------------------------------------------------
   Helpers
   ---------------------------------------------------------------- */

const statusTag = (s: string) => {
  const map: Record<string, string> = {
    WIP: 'bg-blue-100 text-blue-800', draft: 'bg-blue-100 text-blue-800',
    FROZEN: 'bg-orange-100 text-orange-800', frozen: 'bg-orange-100 text-orange-800',
    RELEASED: 'bg-green-100 text-green-800', released: 'bg-green-100 text-green-800',
    OBSOLETE: 'bg-red-100 text-red-800', obsolete: 'bg-red-100 text-red-800',
  };
  return map[s] || 'bg-gray-100 text-gray-800';
};

const statusLabel = (s: string) => {
  const map: Record<string, string> = { WIP: '草稿', draft: '草稿', FROZEN: '冻结', frozen: '冻结', RELEASED: '发布', released: '发布', OBSOLETE: '作废', obsolete: '作废' };
  return map[s] || s;
};

/* ----------------------------------------------------------------
   Component
   ---------------------------------------------------------------- */

export default function AssemblyPartPicker({
  open,
  onClose,
  onConfirm,
  currentAssemblyId,
  existingChildIds = new Set(),
}: AssemblyPartPickerProps) {
  /* ---- 筛选 ---- */
  const [search, setSearch] = useState('');
  const [sortField, setSortField] = useState<string | null>(null);
  const [sortDir, setSortDir] = useState<'asc' | 'desc'>('asc');

  /* ---- 已选 ---- */
  const [selected, setSelected] = useState<Map<string, SelectedItem>>(new Map());

  /* ---- 数据源 ---- */
  const storeParts = useDataStore((s) => s.parts);
  const storeAssemblies = useDataStore((s) => s.assemblies);
  const [fetchedParts, setFetchedParts] = useState<Part[]>([]);
  const [fetchedAssemblies, setFetchedAssemblies] = useState<Assembly[]>([]);
  const [ancestorIds, setAncestorIds] = useState<Set<string>>(new Set());
  const [loading, setLoading] = useState(false);
  const [quickOpen, setQuickOpen] = useState(false);
  const [quickForm, setQuickForm] = useState({ code: '', name: '', spec: '', remark: '' });
  const [quickCreating, setQuickCreating] = useState(false);

  /* 加载数据：store 为空时从 API 拉取；同时计算祖先链 */
  useEffect(() => {
    if (!open) return;
    setQuickForm({ code: '', name: '', spec: '', remark: '' });
    setQuickOpen(false);
    setQuickCreating(false);
    const needParts = storeParts.length === 0;
    const needAssemblies = storeAssemblies.length === 0;
    if (!needParts && !needAssemblies && !currentAssemblyId) {
      setAncestorIds(new Set());
      return;
    }

    setLoading(true);
    const promises: Promise<unknown>[] = [
      needParts ? assembliesApi.list({ page_size: 10000 }).then((r) => r.data) : Promise.resolve(storeParts),
      needAssemblies ? assembliesApi.list({ page_size: 10000 }).then((r) => r.data) : Promise.resolve(storeAssemblies),
    ];

    // 计算祖先链：调用后端接口查询所有父项 PartMaster ID
    if (currentAssemblyId) {
      const wsId = getWorkspaceId();
      assembliesApi.list({ page_size: 1, workspace_id: wsId } as any).then(() => {
        api.get(`/parts/${encodeURIComponent(currentAssemblyId)}/parents`, { params: { workspace_id: wsId } })
          .then(r => {
            const ids = new Set<string>();
            (r.data || []).forEach((a: any) => ids.add(a.id));
            setAncestorIds(ids);
          })
          .catch(() => setAncestorIds(new Set()));
      }).catch(() => setAncestorIds(new Set()));
    }

    Promise.all(promises.slice(0, 2))
      .then(([parts, assemblies]) => {
        setFetchedParts(Array.isArray(parts) ? parts : (parts as any)?.items || []);
        setFetchedAssemblies(Array.isArray(assemblies) ? assemblies : (assemblies as any)?.items || []);
      })
      .catch(() => {})
      .finally(() => setLoading(false));
  }, [open, storeParts, storeAssemblies, currentAssemblyId]);

  const partsList = storeParts.length > 0 ? storeParts : fetchedParts;
  const assembliesList = storeAssemblies.length > 0 ? storeAssemblies : fetchedAssemblies;

  /* 合并所有零件+部件为一个列表 */
  const allCandidates = useMemo<CandidateItem[]>(() => {
    const excludeIds = new Set([
      ...existingChildIds,
      ...ancestorIds,
      ...(currentAssemblyId ? [currentAssemblyId] : []),
    ]);
    const result: CandidateItem[] = [];

    for (const p of partsList) {
      if (!excludeIds.has(p.id)) {
        const pAny = p as any;
        result.push({ id: p.id, code: pAny.number || p.code || '', name: p.name, version: pAny.latestVersion || p.version || 'A', status: pAny.latestStatus || p.status || 'WIP', spec: pAny.spec || pAny.type || '', type: 'part' });
      }
    }
    for (const a of assembliesList) {
      if (!excludeIds.has(a.id)) {
        const aAny = a as any;
        result.push({ id: a.id, code: aAny.number || a.code || '', name: a.name, version: aAny.latestVersion || a.version || 'A', status: aAny.latestStatus || a.status || 'WIP', spec: aAny.spec || aAny.type || '', type: 'component' });
      }
    }
    return result;
  }, [partsList, assembliesList, existingChildIds, ancestorIds, currentAssemblyId]);

  /* 搜索 + 筛选 + 排序 */
  const handlePickerSort = (field: string) => {
    if (sortField === field) setSortDir(d => d === 'asc' ? 'desc' : 'asc');
    else { setSortField(field); setSortDir('asc'); }
  };
  const getPickerSortIcon = (field: string) => {
    if (sortField !== field) return <span className="text-gray-300 ml-0.5">⇅</span>;
    return sortDir === 'asc' ? <span className="text-gray-500 ml-0.5">↑</span> : <span className="text-gray-500 ml-0.5">↓</span>;
  };
  const filtered = useMemo(() => {
    const keyword = search.trim().toLowerCase();
    let result = allCandidates.filter((item) => {
      if (!keyword) return true;
      return (
        item.code.toLowerCase().includes(keyword) ||
        item.name.toLowerCase().includes(keyword)
      );
    });
    if (sortField) {
      result = [...result].sort((a, b) => {
        let va = ''; let vb = '';
        switch (sortField) {
          case 'code': va = a.code; vb = b.code; break;
          case 'name': va = a.name; vb = b.name; break;
        }
        const cmp = va.localeCompare(vb, 'zh-CN');
        return sortDir === 'asc' ? cmp : -cmp;
      });
    }
    return result;
  }, [allCandidates, search, sortField, sortDir]);

  /* ---- 操作 ---- */

  const addToSelected = (item: CandidateItem) => {
    if (selected.has(item.id)) return;
    setSelected(new Map(selected).set(item.id, { ...item, quantity: 1 }));
  };

  const removeFromSelected = (id: string) => {
    const next = new Map(selected);
    next.delete(id);
    setSelected(next);
  };

  const updateQuantity = (id: string, qty: number) => {
    const next = new Map(selected);
    const entry = next.get(id);
    if (entry) next.set(id, { ...entry, quantity: Math.max(1, qty) });
    setSelected(next);
  };

  const handleConfirm = () => {
    const result = Array.from(selected.values()).map((v) => ({
      child_type: v.type === 'part' ? 'part' : 'assembly',
      child_id: v.id,
      quantity: v.quantity,
    }));
    onConfirm(result);
    setSelected(new Map());
    setSearch('');
  };

  const handleCancel = () => {
    setSelected(new Map());
    setSearch('');
    onClose();
  };

  /* 已选列表排序后的数组 */
  const selectedList = useMemo(() => Array.from(selected.values()), [selected]);

  return (
    <Modal open={open} title="添加子项" onClose={handleCancel} width="full" zIndex={60}>
      <div className="space-y-4 max-h-[75vh] flex flex-col">
        {/* ---- 1. 已选子项 ---- */}
        <div className="border rounded-lg overflow-hidden">
          <div className="bg-gray-50 border-b px-4 py-2 flex items-center justify-between">
            <span className="text-sm font-medium text-gray-700">
              已选子项{selectedList.length > 0 ? ` (${selectedList.length})` : ''}
            </span>
          </div>
          {selectedList.length === 0 ? (
            <div className="px-4 py-6 text-center text-sm text-gray-400">请在下方列表中选择要添加的子项</div>
          ) : (
            <div className="overflow-x-auto max-h-48 overflow-y-auto">
              <table className="w-full text-sm">
                <thead className="bg-gray-50 border-b sticky top-0">
                  <tr>
                    <th className="px-3 py-2 text-left text-gray-500 font-medium">件号</th>
                    <th className="px-3 py-2 text-left text-gray-500 font-medium">中文名称</th>
                    <th className="px-3 py-2 text-left text-gray-500 font-medium w-24">用量</th>
                    <th className="px-3 py-2 text-right text-gray-500 font-medium w-12"></th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-gray-100">
                  {selectedList.map((item) => (
                    <tr key={item.id} className="hover:bg-gray-50">
                      <td className="px-3 py-2 font-medium">{item.code}</td>
                      <td className="px-3 py-2">{item.name}</td>
                      <td className="px-3 py-2">
                        <input
                          type="number"
                          min={1}
                          step={1}
                          value={item.quantity}
                          onChange={(e) => updateQuantity(item.id, parseInt(e.target.value, 10) || 1)}
                          className="w-20 px-2 py-1 border border-gray-300 rounded text-right text-sm"
                        />
                      </td>
                      <td className="px-3 py-2 text-right">
                        <button
                          onClick={() => removeFromSelected(item.id)}
                          className="text-red-500 hover:text-red-700 text-xs"
                          title="移除"
                        >
                          ✕
                        </button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>

        {/* ---- 2. 搜索 & 筛选 ---- */}
        <div className="flex gap-2 items-center">
          <input
            type="text"
            placeholder="搜索件号、名称..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className="flex-1 px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-primary-500 text-sm"
          />
        </div>

        {/* ---- 快速新建 ---- */}
        <div className="border rounded-lg overflow-hidden">
          <button onClick={() => setQuickOpen(!quickOpen)} className="w-full px-4 py-2 text-left text-sm text-gray-500 hover:bg-gray-50 flex items-center gap-1">
            <span className="text-xs">{quickOpen ? '▼' : '▶'}</span>
            快速新建零部件
          </button>
          {quickOpen && (
            <div className="px-4 py-3 border-t space-y-2 bg-gray-50">
              <div className="flex gap-2">
                <input value={quickForm.code} onChange={e => setQuickForm({ ...quickForm, code: e.target.value })} placeholder="件号 *" className="flex-1 px-2 py-1.5 text-sm border border-gray-300 rounded focus:outline-none focus:ring-1 focus:ring-primary-500" />
                <input value={quickForm.name} onChange={e => setQuickForm({ ...quickForm, name: e.target.value })} placeholder="名称 *" className="flex-1 px-2 py-1.5 text-sm border border-gray-300 rounded focus:outline-none focus:ring-1 focus:ring-primary-500" />
              </div>
              <div className="flex gap-2">
                <input value={quickForm.spec} onChange={e => setQuickForm({ ...quickForm, spec: e.target.value })} placeholder="规格型号" className="flex-1 px-2 py-1.5 text-sm border border-gray-300 rounded focus:outline-none focus:ring-1 focus:ring-primary-500" />
                <button onClick={async () => {
                  if (!quickForm.code.trim() || !quickForm.name.trim()) return;
                  setQuickCreating(true);
                  try {
                    // 统一走 partMasterApi.create：字段为 number/name/type，且自动注入 workspace_id
                    const r = await partMasterApi.create({ number: quickForm.code.trim(), name: quickForm.name.trim(), type: quickForm.spec.trim() || undefined });
                    const d: any = r.data;
                    const newItem: SelectedItem = { id: d.id, code: d.number || quickForm.code, name: d.name, version: d.latestVersion || 'A', status: d.latestStatus || 'WIP', type: 'part', quantity: 1 };
                    setSelected(prev => new Map(prev).set(newItem.id, newItem));
                    // 同步添加到候选列表，无需重新搜索
                    const candidate: CandidateItem = { id: newItem.id, code: newItem.code, name: newItem.name, version: newItem.version, status: newItem.status, spec: d.type || quickForm.spec || undefined, type: 'part' };
                    setFetchedParts(prev => [...prev, candidate as any]);
                    setQuickForm({ code: '', name: '', spec: '', remark: '' });
                  } catch (e: any) {
                    const detail = e?.response?.data?.detail;
                    alert(typeof detail === 'string' ? `新建失败：${detail}` : '新建零部件失败（件号可能已存在），请重试');
                  } finally { setQuickCreating(false); }
                }} disabled={quickCreating} className="px-4 py-1.5 text-sm bg-primary-600 text-white rounded hover:bg-primary-700 disabled:opacity-50 whitespace-nowrap">
                  {quickCreating ? '创建中...' : '新建并添加'}
                </button>
              </div>
            </div>
          )}
        </div>

        {/* ---- 3. 可选子项列表 ---- */}
        <div className="border rounded-lg overflow-hidden flex-1 min-h-0">
          <div className="overflow-y-auto max-h-64">
            {loading ? (
              <div className="px-4 py-8 text-center text-sm text-gray-400">加载中...</div>
            ) : filtered.length === 0 ? (
              <div className="px-4 py-8 text-center text-sm text-gray-400">无匹配结果</div>
            ) : (
              <table className="w-full text-sm">
                <thead className="bg-gray-50 border-b sticky top-0">
                  <tr>
                    <th onClick={() => handlePickerSort('code')} className="px-3 py-2 text-left text-gray-500 font-medium cursor-pointer select-none whitespace-nowrap">件号 {getPickerSortIcon('code')}</th>
                    <th onClick={() => handlePickerSort('name')} className="px-3 py-2 text-left text-gray-500 font-medium cursor-pointer select-none whitespace-nowrap">中文名称 {getPickerSortIcon('name')}</th>
                    <th className="px-3 py-2 text-left text-gray-500 font-medium w-16">版本</th>
                    <th className="px-3 py-2 text-left text-gray-500 font-medium w-16">状态</th>
                    <th className="px-3 py-2 text-center text-gray-500 font-medium w-20">操作</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-gray-100">
                  {filtered.map((item) => {
                    const isAdded = selected.has(item.id);
                    return (
                      <tr key={item.id} className="hover:bg-gray-50">
                        <td className="px-3 py-2 font-medium">{item.code}</td>
                        <td className="px-3 py-2">{item.name}</td>
                        <td className="px-3 py-2 text-gray-500">{item.version}</td>
                        <td className="px-3 py-2">
                          <span className={`px-1.5 py-0.5 text-xs rounded-full ${statusTag(item.status)}`}>
                            {statusLabel(item.status)}
                          </span>
                        </td>
                        <td className="px-3 py-2 text-center">
                          {isAdded ? (
                            <span className="text-xs text-green-600">已添加</span>
                          ) : (
                            <button
                              onClick={() => addToSelected(item)}
                              className="px-2.5 py-1 text-xs bg-primary-600 text-white rounded hover:bg-primary-700"
                            >
                              添加
                            </button>
                          )}
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            )}
          </div>
        </div>

        {/* ---- 底部操作 ---- */}
        <div className="flex justify-between items-center pt-2 border-t">
          <span className="text-sm text-gray-500">
            已选 <span className="font-medium text-gray-700">{selectedList.length}</span> 项
          </span>
          <div className="flex gap-2">
            <button
              onClick={handleCancel}
              className="px-4 py-2 text-sm border border-gray-300 rounded-lg hover:bg-gray-50"
            >
              取消
            </button>
            <button
              onClick={handleConfirm}
              disabled={selectedList.length === 0}
              className="px-4 py-2 text-sm bg-primary-600 text-white rounded-lg hover:bg-primary-700 disabled:opacity-50"
            >
              确认添加
            </button>
          </div>
        </div>
      </div>
    </Modal>
  );
}
