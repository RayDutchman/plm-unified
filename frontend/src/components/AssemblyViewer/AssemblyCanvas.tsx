/**
 * AssemblyCanvas.tsx
 *
 * 装配体查看器的 R3F Canvas 容器 + 悬浮工具栏。
 *
 * 光照方案：HemisphereLight + 2×DirectionalLight（对齐 DocDoku 设定）。
 * 无 IBL —— PBR 材质在 HemisphereLight 下颜色还原准确，不会"发白"。
 */

import { Suspense, useEffect, useRef, useCallback } from 'react';
import { Canvas, useThree } from '@react-three/fiber';
import { ArcballControls } from '@react-three/drei';
import * as THREE from 'three';
import { AssemblyViewer } from './AssemblyViewer';
import { LODController } from './LODController';
import { useAssemblyStore } from '../../stores/assemblyStore';

/** 半球光 + 背景色 */
function SceneLighting() {
  const { scene } = useThree();
  useEffect(() => {
    scene.background = new THREE.Color('#2a2a2e');
    return () => { scene.background = null; };
  }, [scene]);
  return null;
}

/** 相机控制器 + Escape 取消选中 + 暴露 reset 给工具栏 */
function CameraSetup({ onReady }: { onReady: (reset: () => void) => void }) {
  const selectInstance = useAssemblyStore((s) => s.selectInstance);
  const controlsRef = useRef<any>(null);
  const { camera } = useThree();
  const instances = useAssemblyStore((s) => s.instances);

  useEffect(() => {
    onReady(() => {
      if (!controlsRef.current || instances.length === 0) return;
      const box = new THREE.Box3();
      for (const inst of instances) {
        const mat4 = new THREE.Matrix4().fromArray(inst.matrix);
        const localBox = new THREE.Box3(
          new THREE.Vector3(inst.xMin, inst.yMin, inst.zMin),
          new THREE.Vector3(inst.xMax, inst.yMax, inst.zMax),
        );
        box.union(localBox.applyMatrix4(mat4));
      }
      if (box.isEmpty()) return;
      const center = box.getCenter(new THREE.Vector3());
      const maxDim = Math.max(
        box.max.x - box.min.x,
        box.max.y - box.min.y,
        box.max.z - box.min.z,
      );
      const dist = maxDim * 2;
      camera.position.set(
        center.x + dist * 0.6,
        center.y + dist * 0.5,
        center.z + dist,
      );
      camera.lookAt(center);
      controlsRef.current.target.copy(center);
      controlsRef.current.update();
    });
  }, [instances, camera, onReady]);

  useEffect(() => {
    const onKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape') selectInstance(null);
    };
    window.addEventListener('keydown', onKeyDown);
    return () => window.removeEventListener('keydown', onKeyDown);
  }, [selectInstance]);

  return <ArcballControls ref={controlsRef} makeDefault />;
}

/** 首次加载时自动对准全局包围盒 */
function AutoFit() {
  const { camera } = useThree();
  const instances = useAssemblyStore((s) => s.instances);
  const fitted = useRef(false);

  useEffect(() => {
    if (instances.length === 0 || fitted.current) return;
    fitted.current = true;
    const box = new THREE.Box3();
    for (const inst of instances) {
      const mat4 = new THREE.Matrix4().fromArray(inst.matrix);
      const localBox = new THREE.Box3(
        new THREE.Vector3(inst.xMin, inst.yMin, inst.zMin),
        new THREE.Vector3(inst.xMax, inst.yMax, inst.zMax),
      );
      box.union(localBox.applyMatrix4(mat4));
    }
    if (box.isEmpty()) return;
    const center = box.getCenter(new THREE.Vector3());
    const maxDim = Math.max(
      box.max.x - box.min.x,
      box.max.y - box.min.y,
      box.max.z - box.min.z,
    );
    const dist = maxDim * 2;
    camera.position.set(
      center.x + dist * 0.6,
      center.y + dist * 0.5,
      center.z + dist,
    );
    camera.lookAt(center);
    (camera as THREE.PerspectiveCamera).near = 0.1;
    (camera as THREE.PerspectiveCamera).far = 50000;
    camera.updateProjectionMatrix();
  }, [instances, camera]);

  return null;
}

export function AssemblyCanvas() {
  const instances = useAssemblyStore((s) => s.instances);
  const showEdges = useAssemblyStore((s) => s.showEdges);
  const toggleEdges = useAssemblyStore((s) => s.toggleEdges);
  const resetFnRef = useRef<(() => void) | null>(null);

  const handleReady = useCallback((fn: () => void) => {
    resetFnRef.current = fn;
  }, []);

  const handleScreenshot = () => {
    const canvas = document.querySelector('canvas');
    if (!canvas) return;
    const url = canvas.toDataURL('image/png');
    const ts = new Date().toISOString().replace(/[:.]/g, '-').slice(0, 19);
    const a = document.createElement('a');
    a.href = url;
    a.download = `assembly-${ts}.png`;
    a.click();
  };

  return (
    <div style={{ width: '100%', height: '100%', position: 'relative' }}>
      {/* 悬浮工具栏 */}
      <div style={toolbarStyle}>
        <button onClick={() => resetFnRef.current?.()} title="重置视角" style={btnStyle}>
          ⌂ 重置
        </button>
        <button onClick={handleScreenshot} title="截图" style={btnStyle}>
          📷 截图
        </button>
        <button
          onClick={toggleEdges}
          title="边线开关"
          style={{ ...btnStyle, color: showEdges ? '#93c5fd' : '#6b7280' }}
        >
          ◫ 边线
        </button>
        <span style={{ color: '#9ca3af', fontSize: 12, marginLeft: 4 }}>
          {instances.length} 个实例
        </span>
      </div>

      <Canvas
        camera={{ position: [-1000, -1000, 1000], fov: 45, near: 0.1, far: 50000 }}
        style={{ width: '100%', height: '100%' }}
        gl={{
          preserveDrawingBuffer: true,
          powerPreference: 'high-performance',
          antialias: true,
          stencil: false,
        }}
      >
        <SceneLighting />
        {/* HemisphereLight: 天空蓝灰 + 地面暗橙，强度0.3（对齐 DocDoku） */}
        <hemisphereLight
          args={[0x8899bb, 0x333344, 0.3]}
          position={[0, 500, 0]}
        />
        {/* 主方向光，强度0.6 */}
        <directionalLight position={[200, 200, 1000]} intensity={0.6} />
        {/* 辅方向光，强度0.3，偏左前上方 */}
        <directionalLight position={[-50, 87, 50]} intensity={0.3} />

        <Suspense fallback={null}>
          <LODController />
          <AssemblyViewer />
        </Suspense>

        <AutoFit />
        <CameraSetup onReady={handleReady} />
      </Canvas>
    </div>
  );
}

const toolbarStyle: React.CSSProperties = {
  position: 'absolute', top: 10, left: '50%', transform: 'translateX(-50%)',
  zIndex: 10, display: 'flex', gap: 8, alignItems: 'center',
  background: 'rgba(0,0,0,0.45)', borderRadius: 8,
  padding: '6px 14px', backdropFilter: 'blur(4px)',
};

const btnStyle: React.CSSProperties = {
  background: 'transparent',
  border: '1px solid #4b5563',
  borderRadius: 5,
  color: '#d1d5db',
  padding: '3px 10px',
  fontSize: 12,
  cursor: 'pointer',
};
