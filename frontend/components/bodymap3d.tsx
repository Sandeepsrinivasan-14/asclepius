"use client";
import { Canvas, useFrame } from "@react-three/fiber";
import { OrbitControls } from "@react-three/drei";
import { useRef, useState } from "react";
import * as THREE from "three";

export const STATUS_COLOR: Record<string, string> = { clear: "#3f8f80", watch: "#f2c46d", abnormal: "#ffb454", critical: "#ff5a73" };
type OrganState = { key: string; status: string };
type Props = { organs: OrganState[]; selected: string | null; onSelect: (k: string | null) => void };

function Organ({ id, status, selected, onSelect, position, scale = [1, 1, 1], rotation = [0, 0, 0], pulse = false, children }: {
  id: string; status: string; selected: boolean; onSelect: (k: string | null) => void; position: [number, number, number];
  scale?: [number, number, number]; rotation?: [number, number, number]; pulse?: boolean; children: React.ReactNode;
}) {
  const g = useRef<THREE.Group>(null);
  const [hover, setHover] = useState(false);
  const color = STATUS_COLOR[status] ?? STATUS_COLOR.clear;
  useFrame((s) => {
    if (!g.current) return;
    const beat = pulse ? 1 + Math.max(0, Math.sin(s.clock.elapsedTime * 5.5)) ** 8 * 0.1 : 1;
    const crit = status === "critical" ? 1 + Math.sin(s.clock.elapsedTime * 7) * 0.05 : 1;
    const target = (selected ? 1.18 : hover ? 1.09 : 1) * beat * crit;
    g.current.scale.lerp(new THREE.Vector3(scale[0] * target, scale[1] * target, scale[2] * target), 0.2);
  });
  return (
    <group ref={g} position={position} rotation={rotation} scale={scale}
      onClick={(e) => { e.stopPropagation(); onSelect(selected ? null : id); }}
      onPointerOver={(e) => { e.stopPropagation(); setHover(true); document.body.style.cursor = "pointer"; }}
      onPointerOut={() => { setHover(false); document.body.style.cursor = ""; }}>
      <OrganMesh color={color} intense={selected || hover || status === "critical"}>{children}</OrganMesh>
    </group>
  );
}

function OrganMesh({ color, intense, children }: { color: string; intense: boolean; children: React.ReactNode }) {
  const mat = useRef<THREE.MeshStandardMaterial>(null);
  useFrame(() => { if (mat.current) mat.current.emissiveIntensity += ((intense ? 1.1 : 0.45) - mat.current.emissiveIntensity) * 0.15; });
  return <mesh>{children}<meshStandardMaterial ref={mat} color={color} emissive={color} emissiveIntensity={0.45} roughness={0.35} metalness={0.1} /></mesh>;
}

function Shell() {
  const m = <meshPhysicalMaterial color="#7fd6c4" transparent opacity={0.1} roughness={0.2} depthWrite={false} side={THREE.DoubleSide} />;
  return (
    <group>
      <mesh position={[0, 2.0, 0]}><sphereGeometry args={[0.48, 32, 32]} />{m}</mesh>
      <mesh position={[0, 1.5, 0]}><cylinderGeometry args={[0.16, 0.2, 0.35, 20]} />{m}</mesh>
      <mesh position={[0, 0.45, 0]}><capsuleGeometry args={[0.62, 1.55, 8, 24]} />{m}</mesh>
      <mesh position={[-0.98, 0.65, 0]} rotation={[0, 0, 0.22]}><capsuleGeometry args={[0.15, 1.5, 6, 16]} />{m}</mesh>
      <mesh position={[0.98, 0.65, 0]} rotation={[0, 0, -0.22]}><capsuleGeometry args={[0.15, 1.5, 6, 16]} />{m}</mesh>
      <mesh position={[-0.32, -1.75, 0]}><capsuleGeometry args={[0.22, 2.0, 6, 16]} />{m}</mesh>
      <mesh position={[0.32, -1.75, 0]}><capsuleGeometry args={[0.22, 2.0, 6, 16]} />{m}</mesh>
    </group>
  );
}

function Scene({ organs, selected, onSelect }: Props) {
  const st = (k: string) => organs.find((o) => o.key === k)?.status ?? "clear";
  const common = (k: string) => ({ id: k, status: st(k), selected: selected === k, onSelect });
  const rot = useRef<THREE.Group>(null);
  useFrame((_, d) => { if (rot.current && !selected) rot.current.rotation.y += d * 0.15; });
  return (
    <group ref={rot} position={[0, -0.2, 0]}>
      <Shell />
      <Organ {...common("brain")} position={[0, 2.05, 0]} scale={[1, 0.78, 0.9]}><sphereGeometry args={[0.34, 28, 28]} /></Organ>
      <Organ {...common("thyroid")} position={[0.1, 1.42, 0.12]}><sphereGeometry args={[0.09, 16, 16]} /></Organ>
      <Organ {...common("thyroid")} position={[-0.1, 1.42, 0.12]}><sphereGeometry args={[0.09, 16, 16]} /></Organ>
      <Organ {...common("lungs")} position={[-0.33, 0.85, 0.02]} scale={[0.8, 1.6, 0.7]}><sphereGeometry args={[0.28, 24, 24]} /></Organ>
      <Organ {...common("lungs")} position={[0.33, 0.85, 0.02]} scale={[0.8, 1.6, 0.7]}><sphereGeometry args={[0.28, 24, 24]} /></Organ>
      <Organ {...common("heart")} position={[0.12, 0.72, 0.22]} pulse><sphereGeometry args={[0.2, 24, 24]} /></Organ>
      <Organ {...common("blood")} position={[0, 0.2, -0.1]}><cylinderGeometry args={[0.04, 0.04, 1.9, 12]} /></Organ>
      <Organ {...common("blood")} position={[-0.93, 0.62, 0]} rotation={[0, 0, 0.22]}><cylinderGeometry args={[0.035, 0.035, 1.5, 10]} /></Organ>
      <Organ {...common("blood")} position={[0.93, 0.62, 0]} rotation={[0, 0, -0.22]}><cylinderGeometry args={[0.035, 0.035, 1.5, 10]} /></Organ>
      <Organ {...common("pancreas")} position={[-0.02, 0.1, 0.2]} rotation={[0, 0, Math.PI / 2 + 0.15]}><capsuleGeometry args={[0.07, 0.38, 6, 12]} /></Organ>
      <Organ {...common("gut")} position={[0, -0.35, 0.15]}><torusGeometry args={[0.24, 0.07, 12, 28]} /></Organ>
      <Organ {...common("gut")} position={[0, -0.55, 0.15]} rotation={[0.2, 0, 0]}><torusGeometry args={[0.2, 0.07, 12, 28]} /></Organ>
      <Organ {...common("kidneys")} position={[-0.3, -0.02, -0.18]} scale={[0.7, 1.2, 0.6]}><sphereGeometry args={[0.16, 18, 18]} /></Organ>
      <Organ {...common("kidneys")} position={[0.3, -0.02, -0.18]} scale={[0.7, 1.2, 0.6]}><sphereGeometry args={[0.16, 18, 18]} /></Organ>
    </group>
  );
}

export default function BodyMap3D(props: Props) {
  return (
    <Canvas camera={{ position: [0, -0.1, 13], fov: 38 }} dpr={[1, 1.6]} gl={{ antialias: true, alpha: true }} onPointerMissed={() => props.onSelect(null)}>
      <ambientLight intensity={0.7} />
      <pointLight position={[4, 4, 5]} intensity={40} color="#ffffff" />
      <pointLight position={[-4, -1, 3]} intensity={20} color="#8b7bff" />
      <Scene {...props} />
      <OrbitControls enableZoom={false} enablePan={false} minPolarAngle={Math.PI / 2.8} maxPolarAngle={Math.PI / 1.7} />
    </Canvas>
  );
}
