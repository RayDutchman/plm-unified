/**
 * pages/AssemblyViewerPage.tsx
 *
 * /viewer 路由的页面组件。
 * 从 URL query 参数读取 part / version / workspace_id，
 * 全屏渲染装配体查看器。
 *
 * URL 示例：
 *   /viewer?part=Assem1&version=A
 *   /viewer?part=Assem1&version=A&workspace_id=00000000-0000-0000-0000-000000000001
 */

import { useSearchParams, useNavigate } from 'react-router-dom';
import { AssemblyViewerPage } from '../components/AssemblyViewer';

export default function ViewerPage() {
  const [params] = useSearchParams();
  const navigate = useNavigate();

  const partNumber = params.get('part') ?? '';
  const version = params.get('version') ?? '';
  const workspaceId = params.get('workspace_id') ?? undefined;

  // 参数缺失时给出提示
  if (!partNumber || !version) {
    return (
      <div className="w-screen h-screen flex items-center justify-center bg-[#2a2a2e]">
        <div className="text-center text-gray-400">
          <p className="text-sm">缺少必要参数</p>
          <p className="text-xs mt-1 text-gray-600">URL 格式：/viewer?part=Assem1&version=A</p>
          <button
            onClick={() => navigate(-1)}
            className="mt-4 text-xs text-blue-400 hover:text-blue-300 underline"
          >
            返回
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className="w-screen h-screen">
      <AssemblyViewerPage
        partNumber={partNumber}
        version={version}
        workspaceId={workspaceId}
      />
    </div>
  );
}
