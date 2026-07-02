import { useEffect, useState } from 'react';
import { Modal } from './Modal';
import { partMasterApi, type PartMasterListItem } from '../services/partMasterApi';
import { customFieldsApi, assemblyPartsApi } from '../services/api';
import type { CustomFieldDefinition } from '../types';
import { useDataStore } from '../stores/data';
import EntityDocumentSection from './EntityDocumentSection';
import PartAttachmentBucket from './PartAttachmentBucket';
import AssemblyPartPicker from './AssemblyPartPicker';

interface Props {
  partId: string | null;
  onClose: () => void;
  onSaved: () => void;
}

interface FormData {
  number: string;
  name: string;
  type: string;
  version: string;
  standard_part: boolean;
}

export default function PartMasterEditModal({ partId, onClose, onSaved }: Props) {
  const [loading, setLoading] = useState(false);
  const [editing, setEditing] = useState<PartMasterListItem | null>(null);
  const [formData, setFormData] = useState<FormData>({ number: '', name: '', type: '', version: '', standard_part: false });
  const [saving, setSaving] = useState(false);
  const [saveError, setSaveError] = useState<string | null>(null);
  const [tab, setTab] = useState<'basic' | 'docs' | 'cad' | 'production' | 'bom'>('basic');
  const [customFieldDefs, setCustomFieldDefs] = useState<CustomFieldDefinition[]>([]);
  const [customFieldValues, setCustomFieldValues] = useState<Record<string, unknown>>({});
  const [editParts, setEditParts] = useState<any[]>([]);
  const [loadingEditParts, setLoadingEditParts] = useState(false);
  const [pickerOpen, setPickerOpen] = useState(false);

  useEffect(() => {
    if (!partId) return;
    let cancelled = false;
    (async () => {
      setLoading(true);
      setTab('basic');
      try {
        const r = await partMasterApi.get(partId);
        if (cancelled) return;
        const d = r.data as PartMasterListItem;
        setEditing(d);
        setFormData({
          number: d.number, name: d.name, type: d.type,
          version: d.latestVersion, standard_part: d.standardPart,
        });
        const allDefs = useDataStore.getState().customFieldDefs;
        setCustomFieldDefs(allDefs.filter((df: CustomFieldDefinition) => df.applies_to?.includes('part')));
        try {
          const vr = await customFieldsApi.getValues('part', d.id);
          const vals: Record<string, unknown> = {};
          (vr.data || []).forEach((v: any) => { vals[v.field_id] = v.value; });
          setCustomFieldValues(vals);
        } catch { setCustomFieldValues({}); }
        setLoadingEditParts(true);
        try { const pr = await assemblyPartsApi.list(d.id); setEditParts(pr.data || []); } catch { setEditParts([]); } finally { setLoadingEditParts(false); }
      } catch { if (!cancelled) setEditing(null); }
      finally { if (!cancelled) setLoading(false); }
    })();
    return () => { cancelled = true; };
  }, [partId]);

  const handleSubmit = async () => {
    if (!editing) return;
    setSaving(true);
    setSaveError(null);
    try {
      await partMasterApi.update(editing.id, {
        name: formData.name,
        type: formData.type || undefined,
      });
      const fieldValues = customFieldDefs
        .map((def) => ({ field_id: def.id, value: customFieldValues[def.id] ?? null }))
        .filter((fv) => fv.value !== null && fv.value !== '');
      if (fieldValues.length > 0) {
        await customFieldsApi.setValues('part', editing.id, fieldValues);
      }
      onSaved();
    } catch (err: any) {
      const detail = err?.response?.data?.detail;
      setSaveError(typeof detail === 'string' ? detail : '保存失败');
    } finally {
      setSaving(false);
    }
  };

  const renderCustomFieldInput = (def: CustomFieldDefinition) => {
    const value = customFieldValues[def.id] ?? '';
    const handleChange = (v: unknown) => setCustomFieldValues({ ...customFieldValues, [def.id]: v });
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
      return (
        <input type="number" value={value as string} onChange={(e) => handleChange(e.target.value ? Number(e.target.value) : null)}
          className="w-full text-sm px-2 py-1 border border-gray-200 rounded focus:outline-none focus:ring-2 focus:ring-primary-500" />
      );
    }
    return (
      <input type="text" value={value as string} onChange={(e) => handleChange(e.target.value)}
        className="w-full text-sm px-2 py-1 border border-gray-200 rounded focus:outline-none focus:ring-2 focus:ring-primary-500" />
    );
  };

  return (
    <Modal open={!!partId} title="编辑零部件" onClose={onClose} width="full">
      {loading ? (
        <div className="py-8 text-center text-sm text-gray-400">加载中...</div>
      ) : !editing ? (
        <div className="py-8 text-center text-sm text-gray-400">加载失败</div>
      ) : (
        <div className="flex flex-col" style={{ maxHeight: 'calc(85vh - 80px)' }}>
          {saveError && <div className="text-sm text-red-600 bg-red-50 px-3 py-2 rounded mb-3">{saveError}</div>}
          <div className="flex gap-1 mb-2 border-b flex-wrap shrink-0">
            <TabBtn active={tab === 'basic'} onClick={() => setTab('basic')}>基本信息</TabBtn>
            <TabBtn active={tab === 'docs'} onClick={() => setTab('docs')}>关联图文档</TabBtn>
            <TabBtn active={tab === 'cad'} onClick={() => setTab('cad')}>CAD附件</TabBtn>
            <TabBtn active={tab === 'production'} onClick={() => setTab('production')}>生产附件</TabBtn>
            <TabBtn active={tab === 'bom'} onClick={() => setTab('bom')}>子项清单</TabBtn>
          </div>

          <div className="flex-1 overflow-y-auto min-h-0">
            {tab === 'basic' && (
              <div className="space-y-4">
                <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                  <div className="bg-gray-50 rounded-lg px-3 py-2 border border-gray-100">
                    <label className="block text-xs text-gray-500 mb-0.5">编号</label>
                    <input type="text" value={formData.number} disabled className="w-full text-sm px-2 py-1 border border-gray-200 rounded focus:outline-none disabled:bg-gray-100 disabled:text-gray-400" />
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
                    <input type="text" value={formData.version} disabled className="w-full text-sm px-2 py-1 border border-gray-200 rounded focus:outline-none disabled:bg-gray-100 disabled:text-gray-400" />
                  </div>
                  <div className="bg-gray-50 rounded-lg px-3 py-2 border border-gray-100 flex items-center gap-2">
                    <label className="flex items-center gap-1.5 text-sm cursor-pointer">
                      <input type="checkbox" checked={formData.standard_part} onChange={(e) => setFormData({ ...formData, standard_part: e.target.checked })} className="w-3.5 h-3.5" />
                      标准件
                    </label>
                  </div>
                </div>

                {customFieldDefs.length > 0 && (
                  <div className="border-t pt-4">
                    <h4 className="text-sm font-bold text-gray-700 mb-2">自定义字段</h4>
                    <div className="grid grid-cols-2 md:grid-cols-3 gap-4">
                      {customFieldDefs.map(def => (
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

            {tab === 'docs' && (
              <EntityDocumentSection entityType="assembly" entityId={editing.id} entityCode={editing.number} entityName={editing.name} editable />
            )}

            {tab === 'cad' && (
              <PartAttachmentBucket partId={editing.id} category="cad" label="CAD附件" editable />
            )}

            {tab === 'production' && (
              <PartAttachmentBucket partId={editing.id} category="production" label="生产附件" editable />
            )}

            {tab === 'bom' && (
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
                          <th className="px-3 py-2 text-left text-gray-500 font-medium w-20">层级</th>
                          <th className="px-3 py-2 text-left text-gray-500 font-medium">件号</th>
                          <th className="px-3 py-2 text-left text-gray-500 font-medium">名称</th>
                          <th className="px-3 py-2 text-left text-gray-500 font-medium w-14">版本</th>
                          <th className="px-3 py-2 text-left text-gray-500 font-medium w-16">状态</th>
                          <th className="px-3 py-2 text-center text-gray-500 font-medium w-16">用量</th>
                        </tr>
                      </thead>
                      <tbody className="divide-y divide-gray-100">
                        {editParts.map((p: any, i: number) => (
                          <tr key={i} className="hover:bg-gray-50">
                            <td className="px-3 py-2 text-gray-400">1</td>
                            <td className="px-3 py-2 font-medium">{p.child_detail?.code || p.child_id}</td>
                            <td className="px-3 py-2">{p.child_detail?.name || '-'}</td>
                            <td className="px-3 py-2">{p.child_detail?.version || '-'}</td>
                            <td className="px-3 py-2">{p.child_detail?.status || '-'}</td>
                            <td className="px-3 py-2 text-center">{p.quantity ?? 1}</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  )}
                </div>
              </div>
            )}
          </div>

          <div className="flex-shrink-0 flex justify-end gap-2 pt-2 border-t mt-2">
            <button onClick={onClose} className="px-4 py-2 border border-gray-200 rounded-lg text-sm">取消</button>
            <button onClick={handleSubmit} disabled={saving}
              className="px-4 py-2 bg-primary-600 text-white rounded-lg hover:bg-primary-700 text-sm disabled:opacity-50">
              {saving ? '保存中...' : '保存'}
            </button>
          </div>
        </div>
      )}

      <AssemblyPartPicker open={pickerOpen} onClose={() => setPickerOpen(false)}
        onConfirm={async (items) => {
          if (!editing) return;
          for (const it of items) {
            try { await assemblyPartsApi.add(editing.id, { child_type: it.child_type, child_id: it.child_id, quantity: it.quantity ?? 1 }); } catch {}
          }
          setPickerOpen(false);
          try { const pr = await assemblyPartsApi.list(editing.id); setEditParts(pr.data || []); } catch { setEditParts([]); }
        }}
      />
    </Modal>
  );
}

function TabBtn({ active, onClick, children }: { active: boolean; onClick: () => void; children: React.ReactNode }) {
  return (
    <button onClick={onClick}
      className={`px-4 py-2 text-sm font-medium border-b-2 transition-colors ${active ? 'border-primary-600 text-primary-600' : 'border-transparent text-gray-500 hover:text-gray-700'}`}>
      {children}
    </button>
  );
}
