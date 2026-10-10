"use client";
import { Canvas, useFrame } from "@react-three/fiber";
import { Float, Sparkles } from "@react-three/drei";
import { useMemo, useRef } from "react";
import * as THREE from "three";

function Helix() {
  const g = useRef<THREE.Group>(null);
  const N = 46;
  const pts = useMemo(() => Array.from({ length: N }, (_, i) => { const t = (i / N) * Math.PI * 5; const y = (i / N) * 7 - 3.5; return { t, y }; }), []);
  useFrame((s, d) => { if (g.current) { g.current.rotation.y += d * 0.35; g.current.rotation.z = Math.sin(s.clock.elapsedTime * 0.3) * 0.08; } });
  return (
    <group ref={g}>
      {pts.map((p, i) => (
        <group key={i}>
          <mesh position={[Math.cos(p.t) * 1.15, p.y, Math.sin(p.t) * 1.15]}><sphereGeometry args={[0.09, 16, 16]} /><meshStandardMaterial color="#34d6ae" emissive="#10c295" emissiveIntensity={1.4} /></mesh>
          <mesh position={[Math.cos(p.t + Math.PI) * 1.15, p.y, Math.sin(p.t + Math.PI) * 1.15]}><sphereGeometry args={[0.09, 16, 16]} /><meshStandardMaterial color="#f2c46d" emissive="#f2a93d" emissiveIntensity={1.2} /></mesh>
          {i % 2 === 0 && (
            <mesh position={[0, p.y, 0]} rotation={[0, -p.t, Math.PI / 2]}><cylinderGeometry args={[0.012, 0.012, 2.3, 6]} /><meshStandardMaterial color="#5cc8ff" emissive="#5cc8ff" emissiveIntensity={0.7} transparent opacity={0.55} /></mesh>
          )}
        </group>
      ))}
      <mesh position={[0, 0, 0]}><cylinderGeometry args={[0.03, 0.03, 8, 10]} /><meshStandardMaterial color="#f2c46d" emissive="#f2c46d" emissiveIntensity={0.6} /></mesh>
    </group>
  );
}

export default function HelixScene() {
  return (
    <Canvas camera={{ position: [0, 0, 6.2], fov: 42 }} dpr={[1, 1.6]} gl={{ antialias: true, alpha: true }}>
      <ambientLight intensity={0.5} />
      <pointLight position={[4, 3, 4]} intensity={30} color="#6ee7c8" />
      <pointLight position={[-4, -2, 3]} intensity={22} color="#8b7bff" />
      <Float speed={1.4} rotationIntensity={0.2} floatIntensity={0.6}><Helix /></Float>
      <Sparkles count={70} scale={[8, 8, 6]} size={2.2} speed={0.4} color="#9fe9d6" />
    </Canvas>
  );
}
