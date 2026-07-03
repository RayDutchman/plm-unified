import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { partMasterApi, type PartMasterDetail } from '../services/partMasterApi';
import { customFieldsApi } from '../services/api';
import type { CustomFieldDefinition, CustomFieldValue } from '../types';
import { useDataStore } from '../stores/data';
import { Modal } from './Modal';
import EntityDocumentSection from './EntityDocumentSection';
import PartAttachmentBucket from './PartAttachmentBucket';
import BOMTreeTable from './BOMTreeTable';

const STATUS_MAP: Record<string, { label: string; cls: string }> = {
  WIP: { label: '草稿', cls: 'bg-blue-100 text-blue-800' },
  FROZEN: { label: '冻结', cls: 'bg-orange-100 text-orange-800' },
  RELEASED: { label: '发布', cls: 'bg-green-100 text-green-800' },
  OBSOLETE: { label: '作废', cls: 'bg-red-100 text-red-800' },
};

function statusTag(s: string) {
  return STATUS_MAP[s] || { label: s, cls: 'bg-gray-100 text-gray-800' };
}

interface Props {
  /** 零部件编号或 UUID（后端 GET /api/parts/{id} 两者皆支持）。为 null 时不渲染。 */
  identifier: string | null;
  onClose: () => void;
}

type DetailTab = 'basic' | 'docs' | 'cad' | 'production' | 'bom' | 'versions';

/**
 * 零部件详情弹窗——零部件管理界面（PartMasters）与构型项详情等处共用的唯一详情视图。
 * 自带按 identifier 加载逻辑，调用方只需传入编号/ID。
 */
export default function PartMasterDetailModal({ identifier, onClose }: Props) {
  const [viewing, setViewing] = useState<PartMasterDetail | null>(null);
  const [loading, setLoading] = useState(false);
  const [tab, setTab] = useState<DetailTab>('basic');
  const [customDefs, setCustomDefs] = useState<CustomFieldDefinition[]>([]);
  const [customValues, setCustomValues] = useState<Record<string, unknown>>({});
  const [selIterIdx, setSelIterIdx] = useState(0);  // 0 = latest (default)
  const navigate = useNavigate();

  // 展开所有迭代列表（平坦化，最新排最前）
  const allIterations = (viewing?.revisions || []).flatMap(r =>
    r.iterations.map(it => ({ version: r.version, ...it }))
  ).reverse();

  // 看是否只有一个版本，是的话不显示版本号
  const singleVersion = new Set(allIterations.map(it => it.version)).size <= 1;

  const totalIters = allIterations.length;
  const selectedIter = totalIters > 0 ? allIterations[selIterIdx] : null;

  const selectIter = (delta: number) => {
    setSelIterIdx(prev => Math.max(0, Math.min(totalIters - 1, prev + delta)));
  };
  useEffect(() => {
    if (!identifier) { setViewing(null); return; }
    let cancelled = false;
    setViewing(null);
    setLoading(true);
    setTab('basic');
    setCustomValues({});
    (async () => {
      try {
        const res = await partMasterApi.get(identifier);
        if (cancelled) return;
        const detail = res.data ?? null;
        setViewing(detail);
        const allDefs = useDataStore.getState().customFieldDefs;
        setCustomDefs(allDefs.filter((d: CustomFieldDefinition) => d.applies_to?.includes('part')));
        if (detail) {
          try {
            const valuesRes = await customFieldsApi.getValues('part', detail.id);
            if (cancelled) return;
            const vals: Record<string, unknown> = {};
            (valuesRes.data || []).forEach((v: CustomFieldValue) => { vals[v.field_id] = v.value; });
            setCustomValues(vals);
          } catch { setCustomValues({}); }
        }
      } catch {
        if (!cancelled) setViewing(null);
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => { cancelled = true; };
  }, [identifier]);

  return (
    <Modal open={!!identifier} title="零部件详情" onClose={onClose} width="full">
      {loading ? (
        <div className="py-8 text-center text-sm text-gray-400">加载中...</div>
      ) : !viewing ? (
        <div className="py-8 text-center text-sm text-gray-400">加载失败</div>
      ) : (
        <div className="max-h-[70vh] overflow-y-auto pr-1">
          {totalIters > 0 && (
            <div className="flex items-center justify-center gap-3 mb-3 bg-gray-100 rounded-lg px-3 py-1.5">
              <button onClick={() => selectIter(-1)} disabled={selIterIdx >= totalIters - 1}
                className="text-gray-500 hover:text-gray-800 disabled:opacity-30 text-lg leading-none">◀</button>
              <span className="text-sm font-medium text-gray-700">
                #{selectedIter?.iteration}
                <span className="text-gray-400 font-normal ml-1">
                  ({selIterIdx + 1}/{totalIters})
                </span>
              </span>
              <button onClick={() => selectIter(1)} disabled={selIterIdx <= 0}
                className="text-gray-500 hover:text-gray-800 disabled:opacity-30 text-lg leading-none">▶</button>
            </div>
          )}
          <div className="flex gap-1 mb-4 border-b flex-wrap">
            <TabBtn active={tab === 'basic'} onClick={() => setTab('basic')}>基本信息</TabBtn>
            <TabBtn active={tab === 'docs'} onClick={() => setTab('docs')}>关联图文档</TabBtn>
            <TabBtn active={tab === 'cad'} onClick={() => setTab('cad')}>CAD附件</TabBtn>
            <TabBtn active={tab === 'production'} onClick={() => setTab('production')}>生产附件</TabBtn>
            <TabBtn active={tab === 'bom'} onClick={() => setTab('bom')}>子项清单</TabBtn>
            <TabBtn active={tab === 'versions'} onClick={() => setTab('versions')}>版本历史</TabBtn>
            <div className="ml-auto" />
            <button
              type="button"
              onClick={() => navigate(`/viewer?part=${encodeURIComponent(viewing.number)}&version=${viewing.latestVersion}`)}
              className="px-3 py-1.5 text-xs border border-blue-500 text-blue-500 rounded-md hover:bg-blue-50"
              title="3D 装配体预览"
            >
              📦 3D预览
            </button>
          </div>

          {tab === 'basic' && (
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
              {customDefs.length > 0 && (
                <div className="border-t pt-4">
                  <h4 className="text-sm font-bold text-gray-700 mb-2">自定义字段</h4>
                  <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                    {customDefs.map(def => (
                      <InfoItem key={def.id} label={def.name}
                        value={String(def.field_type === 'select'
                          ? (def.options || []).find(o => o === customValues[def.id]) || customValues[def.id] || '-'
                          : customValues[def.id] ?? '-')} />
                    ))}
                  </div>
                </div>
              )}
            </div>
          )}

          {tab === 'docs' && (
            <EntityDocumentSection entityType="assembly" entityId={viewing.id} entityCode={viewing.number} entityName={viewing.name} editable={false} />
          )}

          {tab === 'cad' && (
            <PartAttachmentBucket partId={viewing.id} category="cad" label="CAD附件" editable={false} />
          )}

          {tab === 'production' && (
            <PartAttachmentBucket partId={viewing.id} category="production" label="生产附件" editable={false} />
          )}

          {tab === 'bom' && (
            <div>
              <h4 className="text-sm font-bold text-gray-700 mb-2">子项清单 ({viewing.childCount})</h4>
              {viewing.childCount === 0 ? (
                <div className="text-sm text-gray-400 py-4 text-center">暂无子项</div>
              ) : (
                <BOMTreeTable assemblyId={viewing.id} />
              )}
            </div>
          )}

          {tab === 'versions' && (
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
