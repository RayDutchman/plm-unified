/**
 * AssemblyCanvas.tsx
 *
 * 装配体查看器的 R3F Canvas + 悬浮工具栏。
 */

import { Suspense, useEffect, useRef, useCallback } from 'react';
import { Canvas, useThree, useFrame } from '@react-three/fiber';
import { ArcballControls } from '@react-three/drei';
import * as THREE from 'three';
import { AssemblyViewer } from './AssemblyViewer';
import { LODController } from './LODController';
import { useAssemblyStore } from '../../stores/assemblyStore';

// ========== 动画状态（模块级，useFrame 驱动） ==========
interface AnimState {
  startPos: THREE.Vector3;
  endPos: THREE.Vector3;
  startTgt: THREE.Vector3;
  endTgt: THREE.Vector3;
  elapsed: number;
  duration: number;
  easing: (t: number) => number;
  ctrl: any;
  camera: THREE.Camera;
}
let gAnim: AnimState | null = null;

function startAnim(
  camera: THREE.Camera,
  ctrl: any,
  endPos: THREE.Vector3,
  endTgt: THREE.Vector3,
  duration: number,
  easing: (t: number) => number,
) {
  gAnim = {
    startPos: camera.position.clone(),
    endPos,
    startTgt: ctrl.target.clone(),
    endTgt,
    elapsed: 0,
    duration,
    easing,
    ctrl,
    camera,
  };
}

// ========== 头灯 ==========
function CameraLights() {
  const { camera } = useThree();
  const d1 = useRef<THREE.DirectionalLight>(null);
  const d2 = useRef<THREE.DirectionalLight>(null);
  const L1 = new THREE.Vector3(0.192, 0.192, 0.961);
  const L2 = new THREE.Vector3(-0.44, 0.77, 0.44);
  useFrame(() => {
    const c = camera.position, q = camera.quaternion;
    if (d1.current) {
      d1.current.position.copy(c).addScaledVector(L1.clone().applyQuaternion(q), 500);
      d1.current.target.position.copy(c);
    }
    if (d2.current) {
      d2.current.position.copy(c).addScaledVector(L2.clone().applyQuaternion(q), 500);
      d2.current.target.position.copy(c);
    }
  });
  return <><directionalLight ref={d1} intensity={0.6}/><directionalLight ref={d2} intensity={0.3}/></>;
}

// ========== 辅助 ==========
const RX = new THREE.Matrix4().makeRotationX(-Math.PI / 2);

function calcBBox(list: ReturnType<typeof useAssemblyStore.getState>['instances']) {
  const box = new THREE.Box3();
  for (const inst of list) {
    const m = new THREE.Matrix4().fromArray(inst.matrix).premultiply(RX);
    box.union(new THREE.Box3(
      new THREE.Vector3(inst.xMin, inst.yMin, inst.zMin),
      new THREE.Vector3(inst.xMax, inst.yMax, inst.zMax),
    ).applyMatrix4(m));
  }
  return box.isEmpty() ? null : box;
}

const DEFAULT_DIR = new THREE.Vector3(1, 1, -1).normalize();

// ========== 首次自动适配 ==========
function AutoFit() {
  const { camera } = useThree();
  const list = useAssemblyStore((s) => s.instances);
  const done = useRef(false);
  useEffect(() => {
    if (list.length === 0 || done.current) return;
    done.current = true;
    const box = calcBBox(list);
    if (!box) return;
    const c = box.getCenter(new THREE.Vector3());
    const r = Math.max(box.max.x-box.min.x, box.max.y-box.min.y, box.max.z-box.min.z);
    camera.position.copy(c).addScaledVector(DEFAULT_DIR, Math.max(r*2, 1));
    camera.lookAt(c);
    (camera as THREE.PerspectiveCamera).near = 0.1;
    (camera as THREE.PerspectiveCamera).far = 50000;
    camera.updateProjectionMatrix();
  }, [list, camera]);
  return null;
}

// ========== Canvas 内动画推进 ==========
function AnimRunner() {
  const { camera } = useThree();
  const ctrlRef = useRef<any>(null);
  // 获取控件的 camera 引用（ArcballControls 的 camera 是 private，但实例相同）
  useEffect(() => {
    // Store camera ref for gAnim
  }, [camera]);
  useFrame((_, delta) => {
    if (!gAnim) return;
    gAnim.elapsed += delta;
    const t = Math.min(gAnim.elapsed / gAnim.duration, 1);
    const e = gAnim.easing(t);
    gAnim.camera.position.lerpVectors(gAnim.startPos, gAnim.endPos, e);
    gAnim.ctrl.setTarget(
      THREE.MathUtils.lerp(gAnim.startTgt.x, gAnim.endTgt.x, e),
      THREE.MathUtils.lerp(gAnim.startTgt.y, gAnim.endTgt.y, e),
      THREE.MathUtils.lerp(gAnim.startTgt.z, gAnim.endTgt.z, e),
    );
    gAnim.camera.lookAt(gAnim.ctrl.target);
    gAnim.ctrl.update();
    if (t >= 1) gAnim = null;
  });
  return null;
}

// ========== 主容器 ==========
export function AssemblyCanvas() {
  const instances = useAssemblyStore((s) => s.instances);
  const showEdges = useAssemblyStore((s) => s.showEdges);
  const toggleEdges = useAssemblyStore((s) => s.toggleEdges);
  const selectInstance = useAssemblyStore((s) => s.selectInstance);
  const controlsRef = useRef<any>(null);
  const cameraRef = useRef<THREE.Camera | null>(null);

  const getCameraAndCtrl = useCallback(() => {
    const ctrl = controlsRef.current;
    const cam = cameraRef.current;
    if (!ctrl || !cam) return null;
    return { ctrl, cam };
  }, []);

  const handleReset = useCallback(() => {
    const pair = getCameraAndCtrl();
    if (!pair || instances.length === 0) return;
    const box = calcBBox(instances);
    const c = box ? box.getCenter(new THREE.Vector3()) : new THREE.Vector3();
    const r = box ? Math.max(box.max.x-box.min.x, box.max.y-box.min.y, box.max.z-box.min.z) : 100;
    const endPos = c.clone().addScaledVector(DEFAULT_DIR, Math.max(r*2, 1));
    startAnim(pair.cam, pair.ctrl, endPos, c, 1.0, (t) => t);
  }, [instances, getCameraAndCtrl]);

  const handleFit = useCallback(() => {
    const pair = getCameraAndCtrl();
    if (!pair || instances.length === 0) return;
    const box = calcBBox(instances);
    if (!box) return;
    const c = box.getCenter(new THREE.Vector3());
    const r = Math.max(box.max.x-box.min.x, box.max.y-box.min.y, box.max.z-box.min.z);
    const dir = c.clone().sub(pair.cam.position).normalize();
    if (dir.lengthSq() < 0.001) dir.copy(DEFAULT_DIR);
    const endPos = c.clone().addScaledVector(dir, -Math.max(r*2, 1));
    startAnim(pair.cam, pair.ctrl, endPos, c, 1.0, (t) => 1 - Math.pow(1-t, 3));
  }, [instances, getCameraAndCtrl]);

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
      <div style={S.toolbar}>
        <button onClick={handleFit} title="最佳适配视图" style={S.btn}>⊡ 适配</button>
        <button onClick={handleReset} title="重置视角" style={S.btn}>⌂ 重置</button>
        <button onClick={handleScreenshot} title="截图" style={S.btn}>📷 截图</button>
        <button onClick={toggleEdges} title="边线开关"
          style={{ ...S.btn, color: showEdges ? '#93c5fd' : '#6b7280' }}>◫ 边线</button>
        <span style={{ color: '#9ca3af', fontSize: 12, marginLeft: 4 }}>{instances.length} 个实例</span>
      </div>

      <Canvas
        camera={{ position: [-1000, -1000, 1000], fov: 45, near: 0.1, far: 50000 }}
        style={{ width: '100%', height: '100%' }}
        gl={{ preserveDrawingBuffer: true, powerPreference: 'high-performance', antialias: true, stencil: false }}
      >
        <SceneBg />
        <hemisphereLight
          args={[new THREE.Color().setHSL(0.6, 0.5, 0.5).getHex(), new THREE.Color().setHSL(0.095, 0.5, 0.4).getHex(), 0.3]}
          position={[0, 500, 0]}
        />
        <CameraLights />
        <Suspense fallback={null}>
          <LODController />
          <group rotation={[-Math.PI / 2, 0, 0]}>
            <AssemblyViewer />
          </group>
        </Suspense>
        <AutoFit />
        <CameraRefCapture onReady={(cam) => { cameraRef.current = cam; }} />
        <ArcballControls ref={controlsRef} makeDefault />
        <AnimRunner />
      </Canvas>
    </div>
  );
}

// ========== 子组件 ==========

function SceneBg() {
  const { scene } = useThree();
  useEffect(() => {
    scene.background = new THREE.Color('#2a2a2e');
    return () => { scene.background = null; };
  }, [scene]);
  return null;
}

function CameraRefCapture({ onReady }: { onReady: (cam: THREE.Camera) => void }) {
  const { camera } = useThree();
  useEffect(() => { onReady(camera); }, [camera, onReady]);
  return null;
}

const S = {
  toolbar: {
    position: 'absolute', top: 10, left: '50%', transform: 'translateX(-50%)',
    zIndex: 10, display: 'flex', gap: 8, alignItems: 'center',
    background: 'rgba(0,0,0,0.45)', borderRadius: 8,
    padding: '6px 14px', backdropFilter: 'blur(4px)',
  } as React.CSSProperties,
  btn: {
    background: 'transparent', border: '1px solid #4b5563',
    borderRadius: 5, color: '#d1d5db', padding: '3px 10px',
    fontSize: 12, cursor: 'pointer',
  } as React.CSSProperties,
};
