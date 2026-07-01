import { useEffect, useState, useMemo } from 'react';
import { partMasterApi, type PartMasterListItem, type PartMasterDetail } from '../services/partMasterApi';
import { customFieldsApi, assemblyPartsApi } from '../services/api';
import type { CustomFieldDefinition, CustomFieldValue } from '../types';
import { useDataStore } from '../stores/data';
import { Modal, ConfirmModal } from '../components/Modal';
import EntityDocumentSection from '../components/EntityDocumentSection';
import PartAttachmentBucket from '../components/PartAttachmentBucket';
import AssemblyPartPicker from '../components/AssemblyPartPicker';
import BOMTreeTable from '../components/BOMTreeTable';

const STATUS_MAP: Record<string, { label: string; cls: string }> = {
  WIP: { label: '草稿', cls: 'bg-blue-100 text-blue-800' },
  FROZEN: { label: '冻结', cls: 'bg-orange-100 text-orange-800' },
  RELEASED: { label: '发布', cls: 'bg-green-100 text-green-800' },
  OBSOLETE: { label: '作废', cls: 'bg-red-100 text-red-800' },
};

function statusTag(s: string) {
  return STATUS_MAP[s] || { label: s, cls: 'bg-gray-100 text-gray-800' };
}

interface FormData {
  number: string;
  name: string;
  type: string;
  version: string;
  standard_part: boolean;
}

const initialForm: FormData = {
  number: '', name: '', type: '', version: 'A', standard_part: false,
};

export default function PartMasters() {
  const [items, setItems] = useState<PartMasterListItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState('');
  const [searchField, setSearchField] = useState('all');
  const [status, setStatus] = useState('');
  const [showAllVersions, setShowAllVersions] = useState(false);

  // 排序
  const [sortField, setSortField] = useState<string | null>('number');
  const [sortDir, setSortDir] = useState<'asc' | 'desc'>('asc');

  // 编辑弹窗
  const [modalOpen, setModalOpen] = useState(false);
  const [editing, setEditing] = useState<PartMasterListItem | null>(null);
  const [formData, setFormData] = useState<FormData>(initialForm);
  const [saving, setSaving] = useState(false);
  const [saveError, setSaveError] = useState<string | null>(null);
  const [deleteId, setDeleteId] = useState<string | null>(null);

  const [editCustomFieldDefs, setEditCustomFieldDefs] = useState<CustomFieldDefinition[]>([]);
  const [editCustomFieldValues, setEditCustomFieldValues] = useState<Record<string, unknown>>({});
  const [editTab, setEditTab] = useState<'basic' | 'docs' | 'cad' | 'production' | 'bom'>('basic');

  const [editParts, setEditParts] = useState<any[]>([]);
  const [loadingEditParts, setLoadingEditParts] = useState(false);
  const [pickerOpen, setPickerOpen] = useState(false);

  const componentCustomDefs = useMemo(() => {
    const allDefs = useDataStore.getState().customFieldDefs;
    return allDefs.filter((d: CustomFieldDefinition) => d.applies_to?.includes('part'));
  }, []);
  const [customFieldValuesMap, setCustomFieldValuesMap] = useState<Record<string, Record<string, unknown>>>({});

  // 详情弹窗
  const [viewing, setViewing] = useState<PartMasterDetail | null>(null);
  const [viewLoading, setViewLoading] = useState(false);
  const [viewCustomDefs, setViewCustomDefs] = useState<CustomFieldDefinition[]>([]);
  const [viewCustomValues, setViewCustomValues] = useState<Record<string, unknown>>({});
  const [detailTab, setDetailTab] = useState<'basic' | 'docs' | 'cad' | 'production' | 'bom' | 'versions'>('basic');

  const load = async (s = '') => {
    setLoading(true);
    try {
      const res = await partMasterApi.list(s ? { search: s } : undefined);
      const data = res.data;
      setItems(Array.isArray(data) ? data : (data?.items ?? []));
    } catch {
      setItems([]);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { load(); }, []);

  useEffect(() => {
    if (items.length === 0) return;
    const allDefs = useDataStore.getState().customFieldDefs;
    const defs = allDefs.filter((d: CustomFieldDefinition) => d.applies_to?.includes('part'));
    if (defs.length === 0) return;
    let cancelled = false;
    (async () => {
      const results = await Promise.allSettled(
        items.map(it => customFieldsApi.getValues('part', it.id))
      );
      if (cancelled) return;
      const map: Record<string, Record<string, unknown>> = {};
      results.forEach((r, i) => {
        if (r.status === 'fulfilled') {
          const vals: Record<string, unknown> = {};
          (r.value.data || []).forEach((v: CustomFieldValue) => { vals[v.field_id] = v.value; });
          map[items[i].id] = vals;
        }
      });
      setCustomFieldValuesMap(map);
    })();
    return () => { cancelled = true; };
  }, [items]);

  const filteredByStatus = useMemo(() => {
    let result = items;
    if (status) result = result.filter((it) => it.latestStatus === status);
    if (search) {
      const kw = search.toLowerCase();
      const match = (v: string | undefined) => v?.toLowerCase().includes(kw);
      if (searchField === 'all') {
        result = result.filter((it) => {
          if (match(it.number) || match(it.name) || match(it.type) || match(it.latestVersion) || match(it.latestStatus)) return true;
          const cfv = customFieldValuesMap[it.id] || {};
          for (const def of componentCustomDefs) {
            const val = cfv[def.id];
            if (val != null && String(val).toLowerCase().includes(kw)) return true;
          }
          return false;
        });
      } else if (searchField === 'number') result = result.filter((it) => match(it.number));
      else if (searchField === 'name') result = result.filter((it) => match(it.name));
      else if (searchField === 'type') result = result.filter((it) => match(it.type));
      else if (searchField === 'version') result = result.filter((it) => match(it.latestVersion));
      else if (searchField === 'status') result = result.filter((it) => match(it.latestStatus));
      else if (searchField.startsWith('cf_')) {
        const fieldId = searchField.replace('cf_', '');
        result = result.filter((it) => {
          const cfv = customFieldValuesMap[it.id] || {};
          const val = cfv[fieldId];
          return val != null && String(val).toLowerCase().includes(kw);
        });
      }
    }
    return result;
  }, [items, search, searchField, status]);

  const versionCountMap: Record<string, number> = {};
  items.forEach((i) => { versionCountMap[i.number] = (versionCountMap[i.number] || 0) + 1; });

  const displayData = useMemo(() => {
    let data = showAllVersions ? filteredByStatus : (() => {
      const latestMap: Record<string, typeof filteredByStatus[0]> = {};
      filteredByStatus.forEach((it) => {
        const existing = latestMap[it.number];
        if (!existing || it.latestVersion > existing.latestVersion) {
          latestMap[it.number] = it;
        }
      });
      return Object.values(latestMap);
    })();
    if (sortField) {
      data = [...data].sort((a, b) => {
        const va = String((a as any)[sortField] ?? '');
        const vb = String((b as any)[sortField] ?? '');
        const cmp = va.localeCompare(vb, 'zh-CN');
        return sortDir === 'asc' ? cmp : -cmp;
      });
    }
    return data;
  }, [filteredByStatus, showAllVersions, sortField, sortDir]);

  const handleSort = (field: string) => {
    if (sortField === field) { setSortDir((d) => (d === 'asc' ? 'desc' : 'asc')); }
    else { setSortField(field); setSortDir('asc'); }
  };

  const getSortIcon = (field: string) => {
    if (sortField !== field) return <span className="text-gray-300 ml-0.5">⇅</span>;
    return sortDir === 'asc' ? <span className="text-gray-500 ml-0.5">↑</span> : <span className="text-gray-500 ml-0.5">↓</span>;
  };

  const handleAdd = () => {
    setEditing(null);
    setFormData(initialForm);
    setModalOpen(true);
  };

  const handleEdit = async (it: PartMasterListItem) => {
    setEditing(it);
    setEditTab('basic');
    setFormData({
      number: it.number, name: it.name, type: it.type,
      version: it.latestVersion, standard_part: it.standardPart,
    });
    const allDefs = useDataStore.getState().customFieldDefs;
    const defs = allDefs.filter((d: CustomFieldDefinition) => d.applies_to?.includes('part'));
    setEditCustomFieldDefs(defs);
    try {
      const valuesRes = await customFieldsApi.getValues('part', it.id);
      const vals: Record<string, unknown> = {};
      (valuesRes.data || []).forEach((v: CustomFieldValue) => { vals[v.field_id] = v.value; });
      setEditCustomFieldValues(vals);
    } catch { setEditCustomFieldValues({}); }
    setLoadingEditParts(true);
    try { const r = await assemblyPartsApi.list(it.id); setEditParts(r.data || []); } catch { setEditParts([]); } finally { setLoadingEditParts(false); }
    setModalOpen(true);
  };

  const handleDelete = async () => {
    if (!deleteId) return;
    try {
      await partMasterApi.delete(deleteId);
      setDeleteId(null);
      load();
    } catch {
      alert('删除失败');
    }
  };

  const handleView = async (it: PartMasterListItem) => {
    setViewing(null);
    setViewLoading(true);
    setDetailTab('basic');
    try {
      const res = await partMasterApi.get(it.number);
      const detail = res.data ?? null;
      setViewing(detail);
      const allDefs = useDataStore.getState().customFieldDefs;
      setViewCustomDefs(allDefs.filter((d: CustomFieldDefinition) => d.applies_to?.includes('part')));
      if (detail) {
        try {
          const valuesRes = await customFieldsApi.getValues('part', detail.id);
          const vals: Record<string, unknown> = {};
          (valuesRes.data || []).forEach((v: CustomFieldValue) => { vals[v.field_id] = v.value; });
          setViewCustomValues(vals);
        } catch { setViewCustomValues({}); }
      }
    } catch {
      setViewing(null);
    } finally {
      setViewLoading(false);
    }
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setSaving(true);
    setSaveError(null);
    try {
      if (editing) {
        await partMasterApi.update(editing.id, {
          name: formData.name,
          type: formData.type || undefined,
        });
        const fieldValues = editCustomFieldDefs
          .map((def) => ({ field_id: def.id, value: editCustomFieldValues[def.id] ?? null }))
          .filter((fv) => fv.value !== null && fv.value !== '');
        if (fieldValues.length > 0) {
          await customFieldsApi.setValues('part', editing.id, fieldValues);
        }
        load();
      } else {
        await partMasterApi.create({
          number: formData.number,
          name: formData.name,
          type: formData.type || undefined,
          standard_part: formData.standard_part,
        });
        load();
      }
      setModalOpen(false);
    } catch (err: any) {
      const detail = err?.response?.data?.detail;
      setSaveError(typeof detail === 'string' ? detail : '保存失败');
    } finally {
      setSaving(false);
    }
  };

  const renderCustomFieldInput = (def: CustomFieldDefinition) => {
    const value = editCustomFieldValues[def.id] ?? '';
    const handleChange = (v: unknown) => setEditCustomFieldValues({ ...editCustomFieldValues, [def.id]: v });
    if (def.field_type === 'select' && def.options?.length) {
      return (
        <select value={value as string} onChange={(e) => handleChange(e.target.value)}
          className="w-full text-sm px-2 py-1 border border-gray-200 rounded focus:outline-none focus:ring-2 focus:ring-primary-500">
          <option value="">请选择</option>
          {def.options.map((opt: string) => <option key={opt} value={opt}>{opt}</option>)}
        </select>
      );
    }
    if (def.field_type === 'number') {
      return <input type="number" value={value as number} onChange={(e) => handleChange(e.target.value ? Number(e.target.value) : null)}
        className="w-full text-sm px-2 py-1 border border-gray-200 rounded focus:outline-none focus:ring-2 focus:ring-primary-500" />;
    }
    if (def.field_type === 'multiselect' && def.options?.length) {
      const selected: string[] = Array.isArray(value) ? value as string[] : [];
      return (
        <div className="flex flex-wrap gap-2">
          {def.options.map((opt: string) => {
            const isChecked = selected.includes(opt);
            return (
              <label key={opt} className="inline-flex items-center gap-1 text-sm">
                <input type="checkbox" checked={isChecked}
                  onChange={() => handleChange(isChecked ? selected.filter((s: string) => s !== opt) : [...selected, opt])}
                  className="rounded" />
                {opt}
              </label>
            );
          })}
        </div>
      );
    }
    return <input type="text" value={value as string} onChange={(e) => handleChange(e.target.value)}
      className="w-full text-sm px-2 py-1 border border-gray-200 rounded focus:outline-none focus:ring-2 focus:ring-primary-500" />;
  };

  return (
    <div className="h-full flex flex-col">
      {/* 列表头部 */}
      <div className="flex items-center gap-2 mb-4 shrink-0">
        <select
          value={searchField}
          onChange={(e) => setSearchField(e.target.value)}
          className="px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-primary-500 bg-white"
        >
          <option value="all">全部字段</option>
          <option value="number">编号</option>
          <option value="name">名称</option>
          <option value="type">类型</option>
          <option value="version">版本</option>
          <option value="status">状态</option>
          {componentCustomDefs.map(def => (
            <option key={def.id} value={`cf_${def.id}`}>{def.name}</option>
          ))}
        </select>
        <input
          type="text"
          placeholder={searchField === 'all' ? '搜索...' : searchField.startsWith('cf_') ? `搜索${componentCustomDefs.find(d => d.id === searchField.replace('cf_', ''))?.name || '自定义字段'}...` : `搜索${searchField === 'number' ? '编号' : searchField === 'name' ? '名称' : searchField === 'type' ? '类型' : searchField === 'version' ? '版本' : '状态'}...`}
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          className="w-44 px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-primary-500"
        />
        <select
          value={status}
          onChange={(e) => setStatus(e.target.value)}
          className="px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-primary-500 bg-white"
        >
          <option value="">全部状态</option>
              <option value="WIP">草稿</option>
              <option value="FROZEN">冻结</option>
              <option value="RELEASED">发布</option>
              <option value="OBSOLETE">作废</option>
        </select>
        <label className="flex items-center gap-1.5 px-3 py-2 border border-gray-300 rounded-lg cursor-pointer hover:bg-gray-50 text-sm whitespace-nowrap">
          <input
            type="checkbox"
            checked={showAllVersions}
            onChange={(e) => setShowAllVersions(e.target.checked)}
            className="w-3.5 h-3.5"
          />
          全部版本
        </label>
        <div className="flex-1" />
        <button onClick={handleAdd} className="px-4 py-2 bg-primary-600 text-white rounded-lg hover:bg-primary-700 text-sm">+ 新增零部件</button>
      </div>

      {/* 列表表格 */}
      <div className="bg-white rounded-lg border border-gray-200 overflow-y-auto flex-1 min-h-0">
        <table className="w-full">
          <thead className="bg-gray-50 border-b border-gray-200 sticky top-0 z-10">
            <tr>
              <th onClick={() => handleSort('number')} className="w-56 px-4 py-3 text-left text-sm font-medium text-gray-500 cursor-pointer hover:text-gray-700 select-none whitespace-nowrap">编号 {getSortIcon('number')}</th>
              <th onClick={() => handleSort('name')} className="w-80 px-4 py-3 text-left text-sm font-medium text-gray-500 cursor-pointer hover:text-gray-700 select-none whitespace-nowrap">名称 {getSortIcon('name')}</th>
              <th onClick={() => handleSort('type')} className="px-4 py-3 text-left text-sm font-medium text-gray-500 cursor-pointer hover:text-gray-700 select-none">类型 {getSortIcon('type')}</th>
               <th onClick={() => handleSort('latestVersion')} className="w-14 px-4 py-3 text-left text-sm font-medium text-gray-500 cursor-pointer hover:text-gray-700 select-none whitespace-nowrap">版本 {getSortIcon('latestVersion')}</th>
              <th onClick={() => handleSort('latestStatus')} className="w-20 px-4 py-3 text-left text-sm font-medium text-gray-500 cursor-pointer hover:text-gray-700 select-none whitespace-nowrap">状态 {getSortIcon('latestStatus')}</th>
              <th className="w-52 px-4 py-3 text-right text-sm font-medium text-gray-500">操作</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-gray-200">
            {loading ? (
              <tr><td colSpan={6} className="px-4 py-8 text-center text-gray-500">加载中...</td></tr>
            ) : displayData.length === 0 ? (
              <tr><td colSpan={6} className="px-4 py-8 text-center text-gray-500">无匹配数据</td></tr>
            ) : (
              displayData.map((it) => (
                <tr key={it.id} className="hover:bg-gray-50 cursor-pointer" onClick={() => handleView(it)}>
                  <td className="px-4 py-3 text-sm font-medium">
                    {it.isAssembly && <span className="mr-1" title="装配体">📦</span>}
                    {it.number}
                    {!showAllVersions && (versionCountMap[it.number] || 0) > 1 && (
                      <span className="ml-1.5 text-xs text-primary-600 bg-primary-50 px-1.5 py-0.5 rounded">{(versionCountMap[it.number] || 0)}个版本</span>
                    )}
                  </td>
                  <td className="px-4 py-3 text-sm">
                    {it.name}
                    {it.standardPart && <span className="ml-1.5 text-xs text-orange-600 bg-orange-50 px-1.5 py-0.5 rounded">标准件</span>}
                  </td>
                  <td className="px-4 py-3 text-sm text-gray-500">{it.type || '-'}</td>
                  <td className="px-4 py-3 text-sm text-gray-500">{it.latestVersion || '-'}</td>
                  <td className="px-4 py-3">
                    <span className={`px-2 py-1 text-xs rounded-full ${statusTag(it.latestStatus).cls}`}>{statusTag(it.latestStatus).label}</span>
                  </td>
                  <td className="px-4 py-3 text-right text-sm" onClick={(e) => e.stopPropagation()}>
                    {it.checkoutUserId && (
                      <span className="mr-3 text-xs text-amber-600 bg-amber-50 px-2 py-0.5 rounded" title="已签出">已签出</span>
                    )}
                    <button onClick={() => handleEdit(it)} className="text-primary-600 hover:text-primary-800 mr-3">编辑</button>
                    <button onClick={() => setDeleteId(it.id)} className="text-red-600 hover:text-red-800">删除</button>
                  </td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>

      {/* 新增/编辑弹窗 */}
      <Modal open={modalOpen} title={editing ? '编辑零部件' : '新增零部件'} onClose={() => setModalOpen(false)} width="full">
        {editing ? (
          <div className="flex flex-col" style={{ maxHeight: 'calc(85vh - 80px)' }}>
            <div className="flex gap-1 mb-2 border-b flex-wrap shrink-0">
              <TabBtn active={editTab === 'basic'} onClick={() => setEditTab('basic')}>基本信息</TabBtn>
              <TabBtn active={editTab === 'docs'} onClick={() => setEditTab('docs')}>关联图文档</TabBtn>
              <TabBtn active={editTab === 'cad'} onClick={() => setEditTab('cad')}>CAD附件</TabBtn>
              <TabBtn active={editTab === 'production'} onClick={() => setEditTab('production')}>生产附件</TabBtn>
              <TabBtn active={editTab === 'bom'} onClick={() => setEditTab('bom')}>子项清单</TabBtn>
            </div>

            <div className="flex-1 overflow-y-auto min-h-0">
              {editTab === 'basic' && (
                <div className="space-y-4">
                  <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                    <div className="bg-gray-50 rounded-lg px-3 py-2 border border-gray-100">
                      <label className="block text-xs text-gray-500 mb-0.5">编号</label>
                      <input type="text" value={formData.number} disabled className="w-full text-sm px-2 py-1 border border-gray-200 rounded focus:outline-none focus:ring-2 focus:ring-primary-500 disabled:bg-gray-100 disabled:text-gray-400" />
                    </div>
                    <div className="bg-gray-50 rounded-lg px-3 py-2 border border-gray-100">
                      <label className="block text-xs text-gray-500 mb-0.5">名称 <span className="text-red-500">*</span></label>
                      <input type="text" value={formData.name} onChange={(e) => setFormData({ ...formData, name: e.target.value })} className="w-full text-sm px-2 py-1 border border-gray-200 rounded focus:outline-none focus:ring-2 focus:ring-primary-500" />
                    </div>
                    <div className="bg-gray-50 rounded-lg px-3 py-2 border border-gray-100">
                      <label className="block text-xs text-gray-500 mb-0.5">类型</label>
                      <input type="text" value={formData.type} onChange={(e) => setFormData({ ...formData, type: e.target.value })} className="w-full text-sm px-2 py-1 border border-gray-200 rounded focus:outline-none focus:ring-2 focus:ring-primary-500" />
                    </div>
                    <div className="bg-gray-50 rounded-lg px-3 py-2 border border-gray-100">
                      <label className="block text-xs text-gray-500 mb-0.5">版本</label>
                      <input type="text" value={formData.version} disabled className="w-full text-sm px-2 py-1 border border-gray-200 rounded focus:outline-none focus:ring-2 focus:ring-primary-500 disabled:bg-gray-100 disabled:text-gray-400" />
                    </div>
                    <div className="bg-gray-50 rounded-lg px-3 py-2 border border-gray-100 flex items-center gap-2">
                      <label className="flex items-center gap-1.5 text-sm cursor-pointer">
                        <input type="checkbox" checked={formData.standard_part} onChange={(e) => setFormData({ ...formData, standard_part: e.target.checked })} className="w-3.5 h-3.5" />
                        标准件
                      </label>
                    </div>
                  </div>

                  {editCustomFieldDefs.length > 0 && (
                    <div className="border-t pt-4">
                      <h4 className="text-sm font-bold text-gray-700 mb-2">自定义字段</h4>
                      <div className="grid grid-cols-2 md:grid-cols-3 gap-4">
                        {editCustomFieldDefs.map(def => (
                          <div key={def.id} className="bg-gray-50 rounded-lg px-3 py-2 border border-gray-100">
                            <label className="block text-xs text-gray-500 mb-0.5">{def.name}</label>
                            {renderCustomFieldInput(def)}
                          </div>
                        ))}
                      </div>
                    </div>
                  )}
                </div>
              )}

              {editTab === 'docs' && (
                <EntityDocumentSection entityType="assembly" entityId={editing.id} entityCode={editing.number} entityName={editing.name} editable />
              )}

              {editTab === 'cad' && (
                <PartAttachmentBucket partId={editing.id} category="cad" label="CAD附件" editable />
              )}

              {editTab === 'production' && (
                <PartAttachmentBucket partId={editing.id} category="production" label="生产附件" editable />
              )}

              {editTab === 'bom' && (
                <div>
                  <div className="flex items-center justify-between mb-2">
                    <h4 className="text-sm font-bold text-gray-700">子项清单 ({editParts.length})</h4>
                    <button type="button" onClick={() => setPickerOpen(true)} className="px-3 py-1 text-sm bg-primary-600 text-white rounded hover:bg-primary-700">+ 添加子项</button>
                  </div>
                  <div className="border rounded-lg overflow-hidden">
                    {loadingEditParts ? (
                      <div className="px-4 py-6 text-center text-sm text-gray-400">加载中...</div>
                    ) : editParts.length === 0 ? (
                      <div className="px-4 py-6 text-center text-sm text-gray-400">暂无子项</div>
                    ) : (
                      <table className="w-full text-sm">
                        <thead className="bg-gray-50 border-b">
                          <tr>
                            <th className="px-3 py-2 text-left text-gray-500 font-medium">件号</th>
                            <th className="px-3 py-2 text-left text-gray-500 font-medium">名称</th>
                            <th className="px-3 py-2 text-left text-gray-500 font-medium w-16">版本</th>
                            <th className="px-3 py-2 text-left text-gray-500 font-medium w-16">状态</th>
                            <th className="px-3 py-2 text-right text-gray-500 font-medium w-20">用量</th>
                            <th className="px-3 py-2 text-center text-gray-500 font-medium w-16">操作</th>
                          </tr>
                        </thead>
                        <tbody className="divide-y divide-gray-100">
                          {editParts.map((p: any) => (
                            <tr key={p.id} className="hover:bg-gray-50">
                              <td className="px-3 py-2 font-medium">{p.child_detail?.code || '-'}</td>
                              <td className="px-3 py-2">{p.child_detail?.name || '-'}</td>
                              <td className="px-3 py-2 text-gray-500">{p.child_detail?.version || '-'}</td>
                              <td className="px-3 py-2">
                                <span className={`px-1.5 py-0.5 text-xs rounded-full ${statusTag(p.child_detail?.status || 'WIP').cls}`}>
                                  {statusTag(p.child_detail?.status || 'WIP').label}
                                </span>
                              </td>
                              <td className="px-3 py-2 text-right">{p.quantity}</td>
                              <td className="px-3 py-2 text-center">
                                <button type="button" onClick={async () => { try { await assemblyPartsApi.remove(editing.id, p.id); const r = await assemblyPartsApi.list(editing.id); setEditParts(r.data || []); } catch { alert('移除失败'); } }} className="text-red-500 hover:text-red-700 text-xs">移除</button>
                              </td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    )}
                  </div>

                  <AssemblyPartPicker
                    open={pickerOpen}
                    onClose={() => setPickerOpen(false)}
                    onConfirm={async (items) => {
                      try {
                        await Promise.all(items.map((it: any) => assemblyPartsApi.add(editing.id, { child_type: it.child_type, child_id: it.child_id, quantity: it.quantity || 1 })));
                        const r = await assemblyPartsApi.list(editing.id);
                        setEditParts(r.data || []);
                        setPickerOpen(false);
                      } catch { alert('添加子项失败'); }
                    }}
                    existingChildIds={new Set(editParts.map((p: any) => p.child_id))}
                    currentAssemblyId={editing.id}
                  />
                </div>
              )}
            </div>

            {saveError && (
              <div className="bg-red-50 border border-red-200 text-red-700 px-4 py-2 rounded-lg text-sm shrink-0 mt-2">{saveError}</div>
            )}
            <div className="flex justify-end gap-2 pt-3 border-t shrink-0 mt-2">
              <button type="button" onClick={() => setModalOpen(false)} className="px-4 py-2 border border-gray-300 rounded-lg hover:bg-gray-50">取消</button>
              <button type="button" onClick={handleSubmit} disabled={saving} className="px-4 py-2 bg-primary-600 text-white rounded-lg hover:bg-primary-700 disabled:opacity-50">{saving ? '保存中...' : '保存'}</button>
            </div>
          </div>
        ) : (
          <form onSubmit={handleSubmit} className="space-y-4">
            <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
              <div className="bg-gray-50 rounded-lg px-3 py-2 border border-gray-100">
                <label className="block text-xs text-gray-500 mb-0.5">编号 <span className="text-red-500">*</span></label>
                <input type="text" value={formData.number} onChange={(e) => setFormData({ ...formData, number: e.target.value })} className="w-full text-sm px-2 py-1 border border-gray-200 rounded focus:outline-none focus:ring-2 focus:ring-primary-500" required />
              </div>
              <div className="bg-gray-50 rounded-lg px-3 py-2 border border-gray-100">
                <label className="block text-xs text-gray-500 mb-0.5">名称 <span className="text-red-500">*</span></label>
                <input type="text" value={formData.name} onChange={(e) => setFormData({ ...formData, name: e.target.value })} className="w-full text-sm px-2 py-1 border border-gray-200 rounded focus:outline-none focus:ring-2 focus:ring-primary-500" required />
              </div>
              <div className="bg-gray-50 rounded-lg px-3 py-2 border border-gray-100">
                <label className="block text-xs text-gray-500 mb-0.5">类型</label>
                <input type="text" value={formData.type} onChange={(e) => setFormData({ ...formData, type: e.target.value })} className="w-full text-sm px-2 py-1 border border-gray-200 rounded focus:outline-none focus:ring-2 focus:ring-primary-500" />
              </div>
              <div className="bg-gray-50 rounded-lg px-3 py-2 border border-gray-100">
                <label className="block text-xs text-gray-500 mb-0.5">版本</label>
                <input type="text" value={formData.version} disabled className="w-full text-sm px-2 py-1 border border-gray-200 rounded focus:outline-none focus:ring-2 focus:ring-primary-500 disabled:bg-gray-100 disabled:text-gray-400" />
              </div>
              <div className="bg-gray-50 rounded-lg px-3 py-2 border border-gray-100 flex items-center gap-2">
                <label className="flex items-center gap-1.5 text-sm cursor-pointer">
                  <input type="checkbox" checked={formData.standard_part} onChange={(e) => setFormData({ ...formData, standard_part: e.target.checked })} className="w-3.5 h-3.5" />
                  标准件
                </label>
              </div>
            </div>
            {saveError && (
              <div className="bg-red-50 border border-red-200 text-red-700 px-4 py-2 rounded-lg text-sm">{saveError}</div>
            )}
            <div className="flex justify-end gap-2 pt-4 border-t">
              <button type="button" onClick={() => setModalOpen(false)} className="px-4 py-2 border border-gray-300 rounded-lg hover:bg-gray-50">取消</button>
              <button type="submit" disabled={saving} className="px-4 py-2 bg-primary-600 text-white rounded-lg hover:bg-primary-700 disabled:opacity-50">{saving ? '保存中...' : '保存'}</button>
            </div>
          </form>
        )}
      </Modal>

      {/* 详情弹窗 */}
      <Modal open={!!viewing || viewLoading} title="零部件详情" onClose={() => setViewing(null)} width="full">
        {viewLoading ? (
          <div className="py-8 text-center text-sm text-gray-400">加载中...</div>
        ) : !viewing ? (
          <div className="py-8 text-center text-sm text-gray-400">加载失败</div>
        ) : (
          <div>
            <div className="flex gap-1 mb-4 border-b flex-wrap">
              <TabBtn active={detailTab === 'basic'} onClick={() => setDetailTab('basic')}>基本信息</TabBtn>
              <TabBtn active={detailTab === 'docs'} onClick={() => setDetailTab('docs')}>关联图文档</TabBtn>
              <TabBtn active={detailTab === 'cad'} onClick={() => setDetailTab('cad')}>CAD附件</TabBtn>
              <TabBtn active={detailTab === 'production'} onClick={() => setDetailTab('production')}>生产附件</TabBtn>
              {viewing.childCount > 0 && <TabBtn active={detailTab === 'bom'} onClick={() => setDetailTab('bom')}>子项清单</TabBtn>}
              {viewing.childCount === 0 && <TabBtn active={detailTab === 'bom'} onClick={() => setDetailTab('bom')}>子项清单</TabBtn>}
              <TabBtn active={detailTab === 'versions'} onClick={() => setDetailTab('versions')}>版本历史</TabBtn>
            </div>

            {detailTab === 'basic' && (
              <div className="space-y-4">
                <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                  <InfoItem label="编号" value={viewing.number} />
                  <InfoItem label="名称" value={viewing.name} />
                  <StatusItem label="状态" status={viewing.latestStatus} />
                  <InfoItem label="版本" value={viewing.latestVersion} />
                  <InfoItem label="类型" value={viewing.type || '-'} />
                  <InfoItem label="标准件" value={viewing.standardPart ? '是' : '否'} />
                  <InfoItem label="签出人" value={viewing.checkoutUserId || '-'} />
                </div>
                {viewCustomDefs.length > 0 && (
                  <div className="border-t pt-4">
                    <h4 className="text-sm font-bold text-gray-700 mb-2">自定义字段</h4>
                    <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                      {viewCustomDefs.map(def => (
                        <InfoItem key={def.id} label={def.name}
                          value={String(def.field_type === 'select'
                            ? (def.options || []).find(o => o === viewCustomValues[def.id]) || viewCustomValues[def.id] || '-'
                            : viewCustomValues[def.id] ?? '-')} />
                      ))}
                    </div>
                  </div>
                )}
              </div>
            )}

            {detailTab === 'docs' && (
              <EntityDocumentSection entityType="assembly" entityId={viewing.id} entityCode={viewing.number} entityName={viewing.name} editable={false} />
            )}

            {detailTab === 'cad' && (
              <PartAttachmentBucket partId={viewing.id} category="cad" label="CAD附件" editable={false} />
            )}

            {detailTab === 'production' && (
              <PartAttachmentBucket partId={viewing.id} category="production" label="生产附件" editable={false} />
            )}

            {detailTab === 'bom' && (
              <div>
                <h4 className="text-sm font-bold text-gray-700 mb-2">子项清单 ({viewing.childCount})</h4>
                {viewing.childCount === 0 ? (
                  <div className="text-sm text-gray-400 py-4 text-center">暂无子项</div>
                ) : (
                  <BOMTreeTable assemblyId={viewing.id} />
                )}
              </div>
            )}

            {detailTab === 'versions' && (
              <div className="space-y-2">
                {viewing.revisions?.map((r) => (
                  <div key={r.version} className="bg-gray-50 rounded-lg px-3 py-2 border border-gray-100 flex items-center gap-3">
                    <span className="text-sm font-medium">{r.version}</span>
                    <span className={`px-2 py-0.5 text-xs rounded-full ${statusTag(r.status).cls}`}>{statusTag(r.status).label}</span>
                    <span className="text-sm text-gray-500">{r.iterations.length} 次迭代</span>
                    {r.iterations.map((it) => (
                      <span key={it.iteration} className="text-xs text-gray-400">
                        #{it.iteration} {it.iterationNote ? `· ${it.iterationNote}` : ''} {it.checkInDate ? `· ${new Date(it.checkInDate).toLocaleDateString('zh-CN')}` : ''}
                      </span>
                    ))}
                  </div>
                ))}
                {(!viewing.revisions || viewing.revisions.length === 0) && (
                  <div className="text-sm text-gray-400 py-4 text-center">暂无版本记录</div>
                )}
              </div>
            )}
          </div>
        )}
      </Modal>

      <ConfirmModal
        open={!!deleteId}
        title="确认删除"
        content="确定要删除该零部件吗？此操作不可撤销。"
        confirmText="删除" cancelText="取消"
        type="danger"
        onConfirm={handleDelete}
        onCancel={() => setDeleteId(null)}
      />
    </div>
  );
}

function InfoItem({ label, value }: { label: string; value: string }) {
  return (
    <div className="bg-gray-50 rounded-lg px-3 py-2 border border-gray-100">
      <div className="text-xs text-gray-500 mb-0.5">{label}</div>
      <div className="text-sm text-gray-900 font-medium whitespace-pre-wrap">{value}</div>
    </div>
  );
}

function StatusItem({ label, status: s }: { label: string; status: string }) {
  const tag = statusTag(s);
  return (
    <div className="bg-gray-50 rounded-lg px-3 py-2 border border-gray-100">
      <div className="text-xs text-gray-500 mb-0.5">{label}</div>
      <span className={`inline-block px-2 py-0.5 text-xs rounded-full ${tag.cls}`}>{tag.label}</span>
    </div>
  );
}

function TabBtn({ active, onClick, children }: { active: boolean; onClick: () => void; children: React.ReactNode }) {
  return (
    <button onClick={onClick} className={`px-4 py-2 text-sm font-medium border-b-2 transition-colors whitespace-nowrap ${active ? 'border-primary-600 text-primary-600' : 'border-transparent text-gray-500 hover:text-gray-700'}`}>
      {children}
    </button>
  );
}
