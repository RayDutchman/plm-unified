import { useEffect, useState, Fragment } from 'react';
import { partMasterApi } from '../services/partMasterApi';
import type { PartMasterListItem, PartMasterDetail } from '../services/partMasterApi';

const STATUS_STYLE: Record<string, string> = {
  WIP: 'bg-amber-100 text-amber-700',
  RELEASED: 'bg-green-100 text-green-700',
  OBSOLETE: 'bg-gray-200 text-gray-500',
};

function StatusBadge({ status }: { status: string }) {
  return (
    <span className={`px-2 py-0.5 rounded text-xs font-medium ${STATUS_STYLE[status] ?? 'bg-gray-100 text-gray-600'}`}>
      {status}
    </span>
  );
}

export default function PartMasters() {
  const [items, setItems] = useState<PartMasterListItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState('');
  const [expanded, setExpanded] = useState<string | null>(null);
  const [details, setDetails] = useState<Record<string, PartMasterDetail>>({});

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

  const toggle = async (number: string) => {
    if (expanded === number) { setExpanded(null); return; }
    setExpanded(number);
    if (!details[number]) {
      try {
        const res = await partMasterApi.get(number);
        if (res.data) setDetails((d) => ({ ...d, [number]: res.data }));
      } catch { /* ignore */ }
    }
  };

  return (
    <div className="p-6">
      <div className="flex items-center justify-between mb-4">
        <h1 className="text-xl font-semibold">零部件管理</h1>
        <button
          className="px-3 py-1.5 bg-blue-600 text-white rounded text-sm hover:bg-blue-700"
          onClick={() => alert('新增零部件（mock 占位）')}
        >
          + 新增零部件
        </button>
      </div>

      <div className="mb-3 flex gap-2">
        <input
          className="border rounded px-3 py-1.5 text-sm w-64"
          placeholder="搜索编号 / 名称"
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          onKeyDown={(e) => { if (e.key === 'Enter') load(search); }}
        />
        <button className="px-3 py-1.5 border rounded text-sm" onClick={() => load(search)}>搜索</button>
      </div>

      <div className="border rounded overflow-hidden">
        <table className="w-full text-sm">
          <thead className="bg-gray-50 text-gray-600">
            <tr>
              <th className="text-left px-3 py-2 font-medium">编号</th>
              <th className="text-left px-3 py-2 font-medium">名称</th>
              <th className="text-left px-3 py-2 font-medium">类型</th>
              <th className="text-left px-3 py-2 font-medium">标准件</th>
              <th className="text-left px-3 py-2 font-medium">最新版本</th>
              <th className="text-left px-3 py-2 font-medium">状态</th>
              <th className="text-left px-3 py-2 font-medium">装配体</th>
              <th className="text-left px-3 py-2 font-medium">签出</th>
            </tr>
          </thead>
          <tbody>
            {loading && (
              <tr><td colSpan={8} className="px-3 py-6 text-center text-gray-400">加载中…</td></tr>
            )}
            {!loading && items.length === 0 && (
              <tr><td colSpan={8} className="px-3 py-6 text-center text-gray-400">暂无零部件</td></tr>
            )}
            {!loading && items.map((it) => (
              <Fragment key={it.number}>
                <tr
                  className="border-t hover:bg-gray-50 cursor-pointer"
                  onClick={() => toggle(it.number)}
                >
                  <td className="px-3 py-2 font-mono">{expanded === it.number ? '▾ ' : '▸ '}{it.number}</td>
                  <td className="px-3 py-2">{it.name}</td>
                  <td className="px-3 py-2 text-gray-600">{it.type}</td>
                  <td className="px-3 py-2">{it.standard_part ? '是' : '—'}</td>
                  <td className="px-3 py-2">{it.latest_version}</td>
                  <td className="px-3 py-2"><StatusBadge status={it.status} /></td>
                  <td className="px-3 py-2">{it.is_assembly ? `📦 ${it.child_count} 子件` : '🔩 零件'}</td>
                  <td className="px-3 py-2 text-gray-600">{it.checkout_user ?? '—'}</td>
                </tr>
                {expanded === it.number && (
                  <tr className="bg-gray-50/60">
                    <td colSpan={8} className="px-6 py-3">
                      <DetailPanel detail={details[it.number]} />
                    </td>
                  </tr>
                )}
              </Fragment>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

function DetailPanel({ detail }: { detail?: PartMasterDetail }) {
  if (!detail) return <div className="text-gray-400 text-sm">加载详情…</div>;
  return (
    <div className="grid grid-cols-2 gap-6">
      <div>
        <div className="text-xs font-semibold text-gray-500 mb-1">版本 / 迭代</div>
        <ul className="space-y-1">
          {detail.revisions.map((r) => (
            <li key={r.version} className="text-sm">
              <span className="font-medium">{r.version}</span> <StatusBadge status={r.status} />
              <span className="text-gray-500"> · {r.iterations.length} 次迭代</span>
              {r.iterations.some((i) => i.iteration_note) && (
                <span className="text-gray-400"> · {r.iterations.find((i) => i.iteration_note)?.iteration_note}</span>
              )}
            </li>
          ))}
        </ul>
      </div>
      <div>
        <div className="text-xs font-semibold text-gray-500 mb-1">
          BOM 子件 {detail.is_assembly ? `(${detail.usage_links.length})` : ''}
        </div>
        {detail.is_assembly ? (
          <table className="w-full text-sm">
            <thead className="text-gray-500">
              <tr><th className="text-left font-normal">子件编号</th><th className="text-left font-normal">名称</th><th className="text-left font-normal">用量</th></tr>
            </thead>
            <tbody>
              {detail.usage_links.map((u) => (
                <tr key={u.component_number}>
                  <td className="font-mono">{u.component_number}</td>
                  <td>{u.component_name}</td>
                  <td>{u.amount} {u.unit}</td>
                </tr>
              ))}
            </tbody>
          </table>
        ) : (
          <div className="text-gray-400 text-sm">叶子零件，无子件</div>
        )}
      </div>
    </div>
  );
}
