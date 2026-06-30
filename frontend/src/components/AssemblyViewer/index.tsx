/**
 * AssemblyViewer/index.tsx
 *
 * 装配体查看器入口组件。
 * 接收顶层 partNumber + version，加载 instances 后渲染 AssemblyCanvas。
 *
 * 用法：
 *   <AssemblyViewerModal
 *     open={true}
 *     partNumber="Assem1"
 *     version="A"
 *     onClose={() => {}}
 *   />
 *
 * 也可以不用 Modal 包裹，直接嵌入到页面某个 div：
 *   <AssemblyViewerPage partNumber="Assem1" version="A" />
 */

import { useEffect } from 'react';
import { AssemblyCanvas } from './AssemblyCanvas';
import { useAssemblyStore } from '../../stores/assemblyStore';
import { useAuthStore } from '../../stores/auth';

interface AssemblyViewerPageProps {
  partNumber: string;
  version: string;
  workspaceId?: string;
}

/** 纯内容组件，不含 Modal 包裹，可直接嵌入到任何容器 */
export function AssemblyViewerPage({ partNumber, version, workspaceId }: AssemblyViewerPageProps) {
  const token = useAuthStore((s) => s.token ?? '');
  const { loadInstances, setWorkspaceId, reset, loading, error, instances } = useAssemblyStore();

  useEffect(() => {
    if (workspaceId) setWorkspaceId(workspaceId);
  }, [workspaceId, setWorkspaceId]);

  useEffect(() => {
    if (!partNumber || !version || !token) return;
    loadInstances(partNumber, version, token);
    return () => reset();
  }, [partNumber, version, token, loadInstances, reset]);

  if (loading) {
    return (
      <div className="flex items-center justify-center w-full h-full bg-[#2a2a2e]">
        <div className="text-center">
          <div className="animate-spin rounded-full h-10 w-10 border-2 border-blue-400 border-t-transparent mx-auto mb-3" />
          <p className="text-gray-400 text-sm">加载装配体实例...</p>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="flex items-center justify-center w-full h-full bg-[#2a2a2e]">
        <div className="text-center text-red-400 text-sm">
          <p>加载失败</p>
          <p className="text-gray-500 text-xs mt-1">{error}</p>
        </div>
      </div>
    );
  }

  if (instances.length === 0) {
    return (
      <div className="flex items-center justify-center w-full h-full bg-[#2a2a2e]">
        <p className="text-gray-500 text-sm">暂无装配体实例数据</p>
      </div>
    );
  }

  return (
    <div className="w-full h-full relative">
      {/* 右上角实例计数 */}
      <div className="absolute top-3 right-3 z-10 bg-black/40 text-gray-300 text-xs px-2 py-1 rounded">
        {instances.length} 个实例
      </div>
      <AssemblyCanvas />
    </div>
  );
}

/** 带 Modal 包裹的版本（便于从零件详情页弹出） */
interface AssemblyViewerModalProps extends AssemblyViewerPageProps {
  open: boolean;
  title?: string;
  onClose: () => void;
}

export function AssemblyViewerModal({
  open,
  partNumber,
  version,
  workspaceId,
  title,
  onClose,
}: AssemblyViewerModalProps) {
  if (!open) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60">
      <div className="w-full h-full max-w-[100vw] max-h-[100vh] bg-[#2a2a2e] flex flex-col">
        {/* Header */}
        <div className="flex items-center justify-between px-4 py-2 bg-[#1e1e22] border-b border-gray-700">
          <span className="text-gray-200 text-sm font-medium">
            {title ?? `装配体预览 - ${partNumber} ${version}`}
          </span>
          <button
            onClick={onClose}
            className="text-gray-400 hover:text-white text-xl leading-none px-2"
            aria-label="关闭"
          >
            ×
          </button>
        </div>
        {/* Body */}
        <div className="flex-1 overflow-hidden">
          <AssemblyViewerPage
            partNumber={partNumber}
            version={version}
            workspaceId={workspaceId}
          />
        </div>
      </div>
    </div>
  );
}
