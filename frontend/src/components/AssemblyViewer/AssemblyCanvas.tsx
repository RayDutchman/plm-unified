/**
 * AssemblyCanvas.tsx
 *
 * 装配体查看器的 R3F Canvas 容器 + 悬浮工具栏。
 *
 * 光照：方向光通过 useFrame 跟随相机旋转（DocDoku "头灯"方案），
 * 确保旋转时没有暗面死角。HalfLight 提供底部/暗面环境补光。
 */

import { Suspense, useEffect, useRef, useCallback } from 'react';
import { Canvas, useThree, useFrame } from '@react-three/fiber';
import { ArcballControls } from '@react-three/drei';
import * as THREE from 'three';
import { AssemblyViewer } from './AssemblyViewer';
import { LODController } from './LODController';
import { useAssemblyStore } from '../../stores/assemblyStore';

// ---------- 背景色 ----------

function SceneBackground() {
  const { scene } = useThree();
  useEffect(() => {
    scene.background = new THREE.Color('#2a2a2e');
    return () => { scene.background = null; };
  }, [scene]);
  return null;
}

// ---------- 相机跟随灯光（头灯方案） ----------

/**
 * 方向光始终从相机视角的固定方向照射，旋转模型时不会出现暗面死角。
 * 对齐 DocDoku SceneManager.addLightsToCamera：
 *   - dirLight1：从前方偏右上照射，强度 0.6
 *   - dirLight2：从左前上方补光，强度 0.3
 */
function CameraLights() {
  const { camera } = useThree();
  const dir1Ref = useRef<THREE.DirectionalLight>(null);
  const dir2Ref = useRef<THREE.DirectionalLight>(null);

  // 跟 DocDoku 对齐的光源方向（相机本地空间）
  const dir1Local = new THREE.Vector3(0.192, 0.192, 0.961);   // set(200,200,1000).normalize()
  const dir2Local = new THREE.Vector3(-0.440, 0.770, 0.440);  // set(-1,1.75,1).normalize()

  useFrame(() => {
    const c = camera.position;
    const q = camera.quaternion;

    if (dir1Ref.current) {
      const d1 = dir1Local.clone().applyQuaternion(q);
      dir1Ref.current.position.copy(c).addScaledVector(d1, 500);
      dir1Ref.current.target.position.copy(c);
    }
    if (dir2Ref.current) {
      const d2 = dir2Local.clone().applyQuaternion(q);
      dir2Ref.current.position.copy(c).addScaledVector(d2, 500);
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

// ---------- 相机控制 ----------

function CameraController({ onReady }: { onReady: (callbacks: Record<string, () => void>) => void }) {
  const selectInstance = useAssemblyStore((s) => s.selectInstance);
  const controlsRef = useRef<any>(null);
  const { camera } = useThree();
  const instances = useAssemblyStore((s) => s.instances);

  const calcGlobalBBox = useCallback(() => {
    const box = new THREE.Box3();
    for (const inst of instances) {
      const mat4 = new THREE.Matrix4().fromArray(inst.matrix);
      const localBox = new THREE.Box3(
        new THREE.Vector3(inst.xMin, inst.yMin, inst.zMin),
        new THREE.Vector3(inst.xMax, inst.yMax, inst.zMax),
      );
      box.union(localBox.applyMatrix4(mat4));
    }
    return box;
  }, [instances]);

  // 暴露给工具栏的回调
  useEffect(() => {
    onReady({
      // DocDoku resetCameraPlace（1000ms, Linear, target=(0,0,0), camUp=(0,0,1)）
      reset: () => {
        if (!controlsRef.current) return;
        const ctrl = controlsRef.current as any;
        const endPos = new THREE.Vector3(-1000, -1000, 1000);
        const endTgt = new THREE.Vector3(0, 0, 0);
        const endUp = new THREE.Vector3(0, 0, 1);
        let elapsed = 0;
        let lastTime = performance.now();
        const startPos = camera.position.clone();
        const startTgt = ctrl.target.clone();
        const startUp = camera.up.clone();
        const loop = () => {
          const now = performance.now();
          elapsed += (now - lastTime) / 1000;
          lastTime = now;
          const t = Math.min(elapsed / 1.0, 1); // Linear
          camera.position.lerpVectors(startPos, endPos, t);
          ctrl.target.lerpVectors(startTgt, endTgt, t);
          camera.up.lerpVectors(startUp, endUp, t);
          camera.lookAt(ctrl.target);
          ctrl.update();
          if (elapsed < 1.0) requestAnimationFrame(loop);
        };
        requestAnimationFrame(loop);
      },

      // DocDoku bestFitView：radius*2（1000ms, Quintic.InOut）
      bestFit: () => {
        if (!controlsRef.current || instances.length === 0) return;
        const box = calcGlobalBBox();
        if (box.isEmpty()) return;
        const ctrl = controlsRef.current as any;
        const center = box.getCenter(new THREE.Vector3());
        const radius = Math.max(
          box.max.x - box.min.x,
          box.max.y - box.min.y,
          box.max.z - box.min.z,
        );
        const dist = Math.max(radius * 2, 1);
        const dir = center.clone().sub(camera.position).normalize();
        if (dir.lengthSq() < 0.001) dir.set(1, 1, -1).normalize();
        const endPos = center.clone().addScaledVector(dir, -dist);

        let elapsed = 0;
        let lastTime = performance.now();
        const startPos = camera.position.clone();
        const startTgt = ctrl.target.clone();
        const loop = () => {
          const now = performance.now();
          elapsed += (now - lastTime) / 1000;
          lastTime = now;
          const t = Math.min(elapsed / 1.0, 1);
          const ease = 1 - Math.pow(1 - t, 3); // Quintic.InOut
          camera.position.lerpVectors(startPos, endPos, ease);
          ctrl.target.lerpVectors(startTgt, center, ease);
          camera.lookAt(ctrl.target);
          ctrl.update();
          if (elapsed < 1.0) requestAnimationFrame(loop);
        };
        requestAnimationFrame(loop);
      },
    });
  }, [instances, camera, onReady, calcGlobalBBox]);

  useEffect(() => {
    const onKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape') selectInstance(null);
    };
    window.addEventListener('keydown', onKeyDown);
    return () => window.removeEventListener('keydown', onKeyDown);
  }, [selectInstance]);

  return <ArcballControls ref={controlsRef} makeDefault />;
}

// ---------- 首次自动适配（仅首次） ----------

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
    const radius = Math.max(
      box.max.x - box.min.x,
      box.max.y - box.min.y,
      box.max.z - box.min.z,
    );
    // DocDoku defaultDirection: {x:1, y:1, z:-1} normalized (from vizReset)
    const dir = new THREE.Vector3(1, 1, -1).normalize();
    const dist = Math.max(radius * 2, 1);
    camera.position.copy(center.clone().addScaledVector(dir, dist));
    camera.lookAt(center);
    (camera as THREE.PerspectiveCamera).near = 0.1;
    (camera as THREE.PerspectiveCamera).far = 50000;
    camera.updateProjectionMatrix();
  }, [instances, camera]);

  return null;
}

// ---------- 主容器 ----------

export function AssemblyCanvas() {
  const instances = useAssemblyStore((s) => s.instances);
  const showEdges = useAssemblyStore((s) => s.showEdges);
  const toggleEdges = useAssemblyStore((s) => s.toggleEdges);
  const callbacksRef = useRef<Record<string, () => void>>({});

  const handleReady = useCallback((callbacks: Record<string, () => void>) => {
    callbacksRef.current = callbacks;
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
        <button onClick={() => callbacksRef.current.bestFit?.()} title="最佳适配视图" style={btnStyle}>
          ⊡ 适配
        </button>
        <button onClick={() => callbacksRef.current.reset?.()} title="重置相机（默认视角）" style={btnStyle}>
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
        camera={{ position: [-1000, -1000, 1000], fov: 45, near: 0.1, far: 50000, up: [0, 0, 1] }}
        style={{ width: '100%', height: '100%' }}
        gl={{
          preserveDrawingBuffer: true,
          powerPreference: 'high-performance',
          antialias: true,
          stencil: false,
        }}
      >
        <SceneBackground />
        {/* 半球光：对齐 DocDoku HSL 颜色 + position(0,0,500) + 强度0.3 */}
        <hemisphereLight args={[new THREE.Color().setHSL(0.6, 0.5, 0.5).getHex(), new THREE.Color().setHSL(0.095, 0.5, 0.4).getHex(), 0.3]} position={[0, 0, 500]} />
        <CameraLights />

        <Suspense fallback={null}>
          <LODController />
          <AssemblyViewer />
        </Suspense>

        <AutoFit />
        <CameraController onReady={handleReady} />
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
