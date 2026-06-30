import { useEffect, useState, useMemo } from 'react';
import { partMasterApi, type PartMasterListItem, type PartMasterDetail } from '../services/partMasterApi';
import { Modal, ConfirmModal } from '../components/Modal';

const STATUS_MAP: Record<string, { label: string; cls: string }> = {
  WIP: { label: '草稿', cls: 'bg-blue-100 text-blue-800' },
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
  status: string;
  standard_part: boolean;
}

const initialForm: FormData = {
  number: '', name: '', type: '', version: 'A', status: 'WIP', standard_part: false,
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

  // 详情弹窗
  const [viewing, setViewing] = useState<PartMasterDetail | null>(null);
  const [detailTab, setDetailTab] = useState<'detail' | 'versions'>('detail');
  const [viewLoading, setViewLoading] = useState(false);

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

  const filteredByStatus = useMemo(() => {
    let result = items;
    if (status) result = result.filter((it) => it.status === status);
    if (search) {
      const kw = search.toLowerCase();
      const match = (v: string | undefined) => v?.toLowerCase().includes(kw);
      if (searchField === 'all') {
        result = result.filter((it) => match(it.number) || match(it.name) || match(it.type) || match(it.latest_version) || match(it.status));
      } else if (searchField === 'number') result = result.filter((it) => match(it.number));
      else if (searchField === 'name') result = result.filter((it) => match(it.name));
      else if (searchField === 'type') result = result.filter((it) => match(it.type));
      else if (searchField === 'version') result = result.filter((it) => match(it.latest_version));
      else if (searchField === 'status') result = result.filter((it) => match(it.status));
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
        if (!existing || it.latest_version > existing.latest_version) {
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

  const handleEdit = (it: PartMasterListItem) => {
    setEditing(it);
    setFormData({
      number: it.number, name: it.name, type: it.type,
      version: it.latest_version, status: it.status, standard_part: it.standard_part,
    });
    setModalOpen(true);
  };

  const handleView = async (it: PartMasterListItem) => {
    setViewing(null);
    setViewLoading(true);
    setDetailTab('detail');
    try {
      const res = await partMasterApi.get(it.number);
      setViewing(res.data ?? null);
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
      await new Promise((r) => setTimeout(r, 300));
      setModalOpen(false);
      alert(editing ? '编辑（mock 占位）' : '新增（mock 占位）');
    } catch {
      setSaveError('保存失败');
    } finally {
      setSaving(false);
    }
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
        </select>
        <input
          type="text"
          placeholder={searchField === 'all' ? '搜索...' : `搜索${searchField === 'number' ? '编号' : searchField === 'name' ? '名称' : searchField === 'type' ? '类型' : searchField === 'version' ? '版本' : '状态'}...`}
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
              <th onClick={() => handleSort('latest_version')} className="w-14 px-4 py-3 text-left text-sm font-medium text-gray-500 cursor-pointer hover:text-gray-700 select-none whitespace-nowrap">版本 {getSortIcon('latest_version')}</th>
              <th onClick={() => handleSort('status')} className="w-20 px-4 py-3 text-left text-sm font-medium text-gray-500 cursor-pointer hover:text-gray-700 select-none whitespace-nowrap">状态 {getSortIcon('status')}</th>
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
                    {it.is_assembly && <span className="mr-1" title="装配体">📦</span>}
                    {it.number}
                    {!showAllVersions && (versionCountMap[it.number] || 0) > 1 && (
                      <span className="ml-1.5 text-xs text-primary-600 bg-primary-50 px-1.5 py-0.5 rounded">{(versionCountMap[it.number] || 0)}个版本</span>
                    )}
                  </td>
                  <td className="px-4 py-3 text-sm">
                    {it.name}
                    {it.standard_part && <span className="ml-1.5 text-xs text-orange-600 bg-orange-50 px-1.5 py-0.5 rounded">标准件</span>}
                  </td>
                  <td className="px-4 py-3 text-sm text-gray-500">{it.type || '-'}</td>
                  <td className="px-4 py-3 text-sm text-gray-500">{it.latest_version || '-'}</td>
                  <td className="px-4 py-3">
                    <span className={`px-2 py-1 text-xs rounded-full ${statusTag(it.status).cls}`}>{statusTag(it.status).label}</span>
                  </td>
                  <td className="px-4 py-3 text-right text-sm" onClick={(e) => e.stopPropagation()}>
                    {it.checkout_user && (
                      <span className="mr-3 text-xs text-amber-600 bg-amber-50 px-2 py-0.5 rounded" title="已签出">{it.checkout_user}</span>
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
        <form onSubmit={handleSubmit} className="space-y-4">
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
            <div className="bg-gray-50 rounded-lg px-3 py-2 border border-gray-100">
              <label className="block text-xs text-gray-500 mb-0.5">编号 <span className="text-red-500">*</span></label>
              <input type="text" value={formData.number} onChange={(e) => setFormData({ ...formData, number: e.target.value })} disabled={!!editing} className="w-full text-sm px-2 py-1 border border-gray-200 rounded focus:outline-none focus:ring-2 focus:ring-primary-500 disabled:bg-gray-100 disabled:text-gray-400" required />
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
            <div className="bg-gray-50 rounded-lg px-3 py-2 border border-gray-100">
              <label className="block text-xs text-gray-500 mb-0.5">状态</label>
              <select value={formData.status} onChange={(e) => setFormData({ ...formData, status: e.target.value })} className="w-full text-sm px-2 py-1 border border-gray-200 rounded focus:outline-none focus:ring-2 focus:ring-primary-500">
                <option value="WIP">草稿</option>
                <option value="RELEASED">发布</option>
                <option value="OBSOLETE">作废</option>
              </select>
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
      </Modal>

      {/* 详情弹窗 */}
      <Modal open={!!viewing || viewLoading} title="零部件详情" onClose={() => setViewing(null)} width="full">
        {viewLoading ? (
          <div className="py-8 text-center text-sm text-gray-400">加载中...</div>
        ) : !viewing ? (
          <div className="py-8 text-center text-sm text-gray-400">加载失败</div>
        ) : (
          <div>
            <div className="flex gap-1 mb-4 border-b">
              <button onClick={() => setDetailTab('detail')} className={`px-4 py-2 text-sm font-medium border-b-2 transition-colors ${detailTab === 'detail' ? 'border-primary-600 text-primary-600' : 'border-transparent text-gray-500 hover:text-gray-700'}`}>基本信息</button>
              <button onClick={() => setDetailTab('versions')} className={`px-4 py-2 text-sm font-medium border-b-2 transition-colors ${detailTab === 'versions' ? 'border-primary-600 text-primary-600' : 'border-transparent text-gray-500 hover:text-gray-700'}`}>版本历史</button>
            </div>

            {detailTab === 'detail' ? (
              <div className="space-y-4">
                <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                  <InfoItem label="编号" value={viewing.number} />
                  <InfoItem label="名称" value={viewing.name} />
                  <StatusItem label="状态" status={viewing.status} />
                  <InfoItem label="版本" value={viewing.latest_version} />
                  <InfoItem label="类型" value={viewing.type || '-'} />
                  <InfoItem label="标准件" value={viewing.standard_part ? '是' : '否'} />
                  <InfoItem label="签出人" value={viewing.checkout_user || '-'} />
                </div>

                {viewing.is_assembly && viewing.usage_links?.length > 0 && (
                  <div className="border-t pt-4">
                    <h4 className="text-sm font-bold text-gray-700 mb-2">BOM 子件 ({viewing.usage_links.length})</h4>
                    <div className="border rounded-lg overflow-hidden">
                      <table className="w-full text-sm">
                        <thead className="bg-gray-50 border-b">
                          <tr>
                            <th className="px-3 py-2 text-left text-gray-500 font-medium">子件编号</th>
                            <th className="px-3 py-2 text-left text-gray-500 font-medium">名称</th>
                            <th className="px-3 py-2 text-right text-gray-500 font-medium w-20">用量</th>
                          </tr>
                        </thead>
                        <tbody className="divide-y divide-gray-100">
                          {viewing.usage_links.map((u) => (
                            <tr key={u.component_number} className="hover:bg-gray-50">
                              <td className="px-3 py-2 font-medium font-mono">{u.component_number}</td>
                              <td className="px-3 py-2">{u.component_name}</td>
                              <td className="px-3 py-2 text-right">{u.amount} {u.unit}</td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                  </div>
                )}
              </div>
            ) : (
              <div className="space-y-2">
                {viewing.revisions?.map((r) => (
                  <div key={r.version} className="bg-gray-50 rounded-lg px-3 py-2 border border-gray-100 flex items-center gap-3">
                    <span className="text-sm font-medium">{r.version}</span>
                    <span className={`px-2 py-0.5 text-xs rounded-full ${statusTag(r.status).cls}`}>{statusTag(r.status).label}</span>
                    <span className="text-sm text-gray-500">{r.iterations.length} 次迭代</span>
                    {r.iterations.map((it) => (
                      <span key={it.iteration} className="text-xs text-gray-400">
                        #{it.iteration} {it.iteration_note ? `· ${it.iteration_note}` : ''} {it.check_in_date ? `· ${new Date(it.check_in_date).toLocaleDateString('zh-CN')}` : ''}
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
        onConfirm={() => { setDeleteId(null); alert('删除（mock 占位）'); }}
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
