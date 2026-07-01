import { Suspense, useEffect } from 'react';
import { Canvas, useThree } from '@react-three/fiber';
import * as THREE from 'three';
import { RoomEnvironment } from 'three/examples/jsm/environments/RoomEnvironment.js';
import { ModelLoader } from './ModelLoader';
import { PartHighlighter } from './PartHighlighter';
import { GLTFErrorBoundary } from './GLTFErrorBoundary';
import { SectionPlanes } from './SectionPlanes';
import { MeasureTool } from './MeasureTool';
import { ExplodeView } from './ExplodeView';
import { CameraController } from './CameraController';
import { useViewerStore } from '../../stores/viewerStore';
/**
 * P2.1 截图处理器：监听 screenshotTrigger，执行 canvas.toDataURL 并下载。
 * 必须在 Canvas 内部才能拿到 gl.domElement。
 */
function ScreenshotHandler() {
  const { gl } = useThree();
  const screenshotTrigger = useViewerStore((s) => s.screenshotTrigger);
  useEffect(() => {
    if (screenshotTrigger === 0) return;
    // preserveDrawingBuffer: true 保证任意时刻 toDataURL 都能取到内容
    const url = gl.domElement.toDataURL('image/png');
    const ts = new Date().toISOString().replace(/[:.]/g, '-').slice(0, 19);
    const a = document.createElement('a');
    a.href = url;
    a.download = `viewer-${ts}.png`;
    a.style.display = 'none';
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
  }, [screenshotTrigger, gl]);
  return null;
}

/**
 * 程序化室内环境光（three 内置 RoomEnvironment + PMREMGenerator）。
 * 为 MeshStandardMaterial 提供基于图像的环境光照(IBL)与反射，
 * 完全本地生成、无任何外部文件/CDN 依赖，替代原 <Environment preset>。
 */
function LocalEnvironment() {
  const { gl, scene } = useThree();
  useEffect(() => {
    const pmrem = new THREE.PMREMGenerator(gl);
    const envMap = pmrem.fromScene(new RoomEnvironment(), 0.04).texture;
    scene.environment = envMap;
    // P1.4：IBL 强度提升（0.8→1.0），PBR 金属面高光更自然
    scene.environmentIntensity = 1.0;
    // P1.1：深色背景，接近 CATIA 原生查看器风格
    scene.background = new THREE.Color('#2a2a2e');
    return () => {
      scene.environment = null;
      scene.background = null;
      envMap.dispose();
      pmrem.dispose();
    };
  }, [gl, scene]);
  return null;
}

interface ViewerCanvasProps {
  url: string;
}

export function ViewerCanvas({ url }: ViewerCanvasProps) {
  const selectNode = useViewerStore((s) => s.selectNode);

  useEffect(() => {
    const onKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape') selectNode(null);
    };
    window.addEventListener('keydown', onKeyDown);
    return () => window.removeEventListener('keydown', onKeyDown);
  }, [selectNode]);

  return (
    <Canvas
      camera={{ position: [5, 5, 5] }}
      style={{ width: '100%', height: '100%' }}
       gl={{
        preserveDrawingBuffer: true,
        powerPreference: 'high-performance',
        // P1.2：开启 MSAA 抗锯齿，工程零件尖锐边缘效果明显
        antialias: true,
        stencil: false,
      }}
    >
      <LocalEnvironment />
      <ScreenshotHandler />
      {/* P1.4：加强方向光（适配深色背景） */}
      <ambientLight intensity={0.35} />
      <directionalLight position={[10, 10, 5]} intensity={0.9} />
      <directionalLight position={[-8, 4, -6]} intensity={0.5} />
      <Suspense fallback={null}>
        <GLTFErrorBoundary>
          <ModelLoader url={url} />
          <PartHighlighter url={url} />
        </GLTFErrorBoundary>
      </Suspense>
      <SectionPlanes />
      <MeasureTool />
      <ExplodeView />
      <CameraController />
    </Canvas>
  );
}
