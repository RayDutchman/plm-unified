/**
 * AssemblyCanvas.tsx
 *
 * 装配体查看器的 R3F Canvas + 悬浮工具栏。
 *
 * 约定：Three.js 默认 Y-up；CAD 数据 (Z-up) 通过根 group rotation 转换为 Y-up。
 * 这样 ArcballControls 旋转手感正常，场景中的模型方向也正确。
 */

import { Suspense, useEffect, useRef, useCallback } from 'react';
import { Canvas, useThree, useFrame } from '@react-three/fiber';
import { ArcballControls } from '@react-three/drei';
import * as THREE from 'three';
import { AssemblyViewer } from './AssemblyViewer';
import { LODController } from './LODController';
import { useAssemblyStore } from '../../stores/assemblyStore';

// ========== 背景 ==========
function SceneBackground() {
  const { scene } = useThree();
  useEffect(() => {
    scene.background = new THREE.Color('#2a2a2e');
    return () => { scene.background = null; };
  }, [scene]);
  return null;
}

// ========== 头灯 ==========
function CameraLights() {
  const { camera } = useThree();
  const dir1Ref = useRef<THREE.DirectionalLight>(null);
  const dir2Ref = useRef<THREE.DirectionalLight>(null);
  const dir1Local = new THREE.Vector3(0.192, 0.192, 0.961);
  const dir2Local = new THREE.Vector3(-0.440, 0.770, 0.440);

  useFrame(() => {
    const c = camera.position;
    const q = camera.quaternion;
    if (dir1Ref.current) {
      dir1Ref.current.position.copy(c).addScaledVector(dir1Local.clone().applyQuaternion(q), 500);
      dir1Ref.current.target.position.copy(c);
    }
    if (dir2Ref.current) {
      dir2Ref.current.position.copy(c).addScaledVector(dir2Local.clone().applyQuaternion(q), 500);
      dir2Ref.current.target.position.copy(c);
    }
  });

  return (
    <>
      <directionalLight ref={dir1Ref} intensity={0.6} />
      <directionalLight ref={dir2Ref} intensity={0.3} />
    </>
  );
}

// ========== 辅助 ==========
function calcBBox(instances: ReturnType<typeof useAssemblyStore.getState>['instances']) {
  const box = new THREE.Box3();
  const toYup = new THREE.Matrix4().makeRotationX(-Math.PI / 2);
  for (const inst of instances) {
    const mat4 = new THREE.Matrix4().fromArray(inst.matrix).premultiply(toYup);
    const localBox = new THREE.Box3(
      new THREE.Vector3(inst.xMin, inst.yMin, inst.zMin),
      new THREE.Vector3(inst.xMax, inst.yMax, inst.zMax),
    );
    box.union(localBox.applyMatrix4(mat4));
  }
  return box.isEmpty() ? null : box;
}

const quintic = (t: number) => 1 - Math.pow(1 - t, 3);

function animateCameraView(
  camera: THREE.Camera,
  ctrl: any,
  startPos: THREE.Vector3,
  endPos: THREE.Vector3,
  startTgt: THREE.Vector3,
  endTgt: THREE.Vector3,
  duration: number,
  easing: (t: number) => number,
) {
  let elapsed = 0;
  let last = performance.now();
  const loop = () => {
    const now = performance.now();
    elapsed += (now - last) / 1000;
    last = now;
    const t = Math.min(elapsed / duration, 1);
    const e = easing(t);
    camera.position.lerpVectors(startPos, endPos, e);
    ctrl.target.lerpVectors(startTgt, endTgt, e);
    camera.lookAt(ctrl.target);
    ctrl.update();
    if (elapsed < duration) requestAnimationFrame(loop);
  };
  requestAnimationFrame(loop);
}

// ========== 首次自动适配 ==========
function AutoFit() {
  const { camera } = useThree();
  const instances = useAssemblyStore((s) => s.instances);
  const fitted = useRef(false);
  useEffect(() => {
    if (instances.length === 0 || fitted.current) return;
    fitted.current = true;
    const box = calcBBox(instances);
    if (!box) return;
    const c = box.getCenter(new THREE.Vector3());
    const r = Math.max(box.max.x - box.min.x, box.max.y - box.min.y, box.max.z - box.min.z);
    const dir = new THREE.Vector3(1, 1, -1).normalize();
    camera.position.copy(c).addScaledVector(dir, Math.max(r * 2, 1));
    camera.lookAt(c);
    (camera as THREE.PerspectiveCamera).near = 0.1;
    (camera as THREE.PerspectiveCamera).far = 50000;
    camera.updateProjectionMatrix();
  }, [instances, camera]);
  return null;
}

// ========== 主容器 ==========
export function AssemblyCanvas() {
  const instances = useAssemblyStore((s) => s.instances);
  const showEdges = useAssemblyStore((s) => s.showEdges);
  const toggleEdges = useAssemblyStore((s) => s.toggleEdges);
  const selectInstance = useAssemblyStore((s) => s.selectInstance);
  const controlsRef = useRef<any>(null);

  const toYup = new THREE.Matrix4().makeRotationX(-Math.PI / 2);
  const fromYup = new THREE.Matrix4().makeRotationX(Math.PI / 2);

  /** 默认方向（Y-up坐标系下）：前右上 (1,1,-1)归一化 */
  const defaultDir = useCallback(
    () => new THREE.Vector3(1, 1, -1).normalize(),
    [],
  );

  const handleReset = useCallback(() => {
    const ctrl = controlsRef.current;
    if (!ctrl || instances.length === 0) return;
    const box = calcBBox(instances);
    const center = box ? box.getCenter(new THREE.Vector3()) : new THREE.Vector3();
    const r = box ? Math.max(box.max.x - box.min.x, box.max.y - box.min.y, box.max.z - box.min.z) : 100;
    const dir = defaultDir();
    const endPos = center.clone().addScaledVector(dir, Math.max(r * 2, 1));
    const cam = (ctrl as any)._camera as THREE.Camera;
    const target = (ctrl as any)._gizmoMatrixState as THREE.Vector3;
    animateCameraView(cam, ctrl, cam.position.clone(), endPos, target.clone(), center, 1.0, (t) => t);
  }, [instances, defaultDir]);

  const handleFit = useCallback(() => {
    const ctrl = controlsRef.current;
    if (!ctrl || instances.length === 0) return;
    const box = calcBBox(instances);
    if (!box) return;
    const center = box.getCenter(new THREE.Vector3());
    const r = Math.max(box.max.x - box.min.x, box.max.y - box.min.y, box.max.z - box.min.z);
    const cam = (ctrl as any)._camera as THREE.Camera;
    const target = (ctrl as any)._gizmoMatrixState as THREE.Vector3;
    const dir = center.clone().sub(cam.position).normalize();
    if (dir.lengthSq() < 0.001) dir.copy(defaultDir());
    const endPos = center.clone().addScaledVector(dir, -Math.max(r * 2, 1));
    animateCameraView(cam, ctrl, cam.position.clone(), endPos, target.clone(), center, 1.0, quintic);
  }, [instances, defaultDir]);

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

  useEffect(() => {
    const onKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape') selectInstance(null);
    };
    window.addEventListener('keydown', onKeyDown);
    return () => window.removeEventListener('keydown', onKeyDown);
  }, [selectInstance]);

  return (
    <div style={{ width: '100%', height: '100%', position: 'relative' }}>
      <div style={toolbarStyle}>
        <button onClick={handleFit} title="最佳适配视图" style={btnStyle}>⊡ 适配</button>
        <button onClick={handleReset} title="重置视角" style={btnStyle}>⌂ 重置</button>
        <button onClick={handleScreenshot} title="截图" style={btnStyle}>📷 截图</button>
        <button onClick={toggleEdges} title="边线开关" style={{ ...btnStyle, color: showEdges ? '#93c5fd' : '#6b7280' }}>◫ 边线</button>
        <span style={{ color: '#9ca3af', fontSize: 12, marginLeft: 4 }}>{instances.length} 个实例</span>
      </div>

      <Canvas
        camera={{ position: [-1000, -1000, 1000], fov: 45, near: 0.1, far: 50000 }}
        style={{ width: '100%', height: '100%' }}
        gl={{ preserveDrawingBuffer: true, powerPreference: 'high-performance', antialias: true, stencil: false }}
      >
        <SceneBackground />
        <hemisphereLight
          args={[new THREE.Color().setHSL(0.6, 0.5, 0.5).getHex(), new THREE.Color().setHSL(0.095, 0.5, 0.4).getHex(), 0.3]}
          position={[0, 500, 0]}
        />
        <CameraLights />

        <Suspense fallback={null}>
          <LODController />
          {/* Z-up (CAD) → Y-up (Three.js)：根 group 绕 X 轴旋转 -90° */}
          <group rotation={[-Math.PI / 2, 0, 0]}>
            <AssemblyViewer />
          </group>
        </Suspense>

        <AutoFit />
        <ArcballControls ref={controlsRef} makeDefault />
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
  background: 'transparent', border: '1px solid #4b5563',
  borderRadius: 5, color: '#d1d5db', padding: '3px 10px',
  fontSize: 12, cursor: 'pointer',
};
