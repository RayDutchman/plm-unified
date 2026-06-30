/**
 * AssemblyCanvas.tsx
 *
 * 装配体查看器的 R3F Canvas 容器 + 悬浮工具栏。
 * 组合：LocalEnvironment + 光照 + CameraController + LODController + AssemblyViewer
 */

import { Suspense, useEffect, useRef, useCallback } from 'react';
import { Canvas, useThree } from '@react-three/fiber';
import { ArcballControls } from '@react-three/drei';
import * as THREE from 'three';
import { RoomEnvironment } from 'three/examples/jsm/environments/RoomEnvironment.js';
import { AssemblyViewer } from './AssemblyViewer';
import { LODController } from './LODController';
import { useAssemblyStore } from '../../stores/assemblyStore';

/** 程序化 IBL 环境光（本地生成，不依赖外网）
 *  environmentIntensity 调低到 0.7，配合材质 roughness=0.6/metalness=0.15，避免过曝发白。
 */
function LocalEnvironment() {
  const { gl, scene } = useThree();
  useEffect(() => {
    const pmrem = new THREE.PMREMGenerator(gl);
    const envMap = pmrem.fromScene(new RoomEnvironment(), 0.04).texture;
    scene.environment = envMap;
    scene.environmentIntensity = 0.7;   // ← 从 1.0 降到 0.7
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

/** 相机控制器：ArcballControls + Escape 取消选中 + 暴露 resetCamera ref */
function CameraSetup({ onReady }: { onReady: (reset: () => void) => void }) {
  const selectInstance = useAssemblyStore((s) => s.selectInstance);
  const controlsRef = useRef<any>(null);
  const { camera } = useThree();
  const instances = useAssemblyStore((s) => s.instances);

  // 暴露重置函数给外层工具栏
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
        localBox.applyMatrix4(mat4);
        box.union(localBox);
      }
      if (box.isEmpty()) return;
      const center = box.getCenter(new THREE.Vector3());
      const size = box.getSize(new THREE.Vector3());
      const maxDim = Math.max(size.x, size.y, size.z);
      const dist = maxDim * 1.8;
      camera.position.set(center.x + dist * 0.6, center.y + dist * 0.5, center.z + dist);
      camera.lookAt(center);
      camera.updateProjectionMatrix();
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
      localBox.applyMatrix4(mat4);
      box.union(localBox);
    }
    if (box.isEmpty()) return;

    const center = box.getCenter(new THREE.Vector3());
    const size = box.getSize(new THREE.Vector3());
    const maxDim = Math.max(size.x, size.y, size.z);
    const dist = maxDim * 1.8;

    camera.position.set(center.x + dist * 0.6, center.y + dist * 0.5, center.z + dist);
    camera.lookAt(center);
    (camera as THREE.PerspectiveCamera).near = maxDim * 0.001;
    (camera as THREE.PerspectiveCamera).far = maxDim * 100;
    camera.updateProjectionMatrix();
  }, [instances, camera]);

  return null;
}

export function AssemblyCanvas() {
  const instances = useAssemblyStore((s) => s.instances);
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
      <div
        style={{
          position: 'absolute', top: 10, left: '50%', transform: 'translateX(-50%)',
          zIndex: 10, display: 'flex', gap: 8, alignItems: 'center',
          background: 'rgba(0,0,0,0.45)', borderRadius: 8,
          padding: '6px 14px', backdropFilter: 'blur(4px)',
        }}
      >
        <button
          onClick={() => resetFnRef.current?.()}
          title="重置视角"
          style={btnStyle}
        >
          ⌂ 重置
        </button>
        <button onClick={handleScreenshot} title="截图" style={btnStyle}>
          📷 截图
        </button>
        <span style={{ color: '#9ca3af', fontSize: 12, marginLeft: 4 }}>
          {instances.length} 个实例
        </span>
      </div>

      <Canvas
        camera={{ position: [10, 8, 10], fov: 45 }}
        style={{ width: '100%', height: '100%' }}
        gl={{
          preserveDrawingBuffer: true,
          powerPreference: 'high-performance',
          antialias: true,
          stencil: false,
        }}
      >
        <LocalEnvironment />
        {/* 主光源强度降低，配合低 roughness 避免过曝 */}
        <ambientLight intensity={0.25} />
        <directionalLight position={[10, 10, 5]} intensity={0.7} />
        <directionalLight position={[-8, 4, -6]} intensity={0.4} />

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

const btnStyle: React.CSSProperties = {
  background: 'transparent',
  border: '1px solid #4b5563',
  borderRadius: 5,
  color: '#d1d5db',
  padding: '3px 10px',
  fontSize: 12,
  cursor: 'pointer',
};
