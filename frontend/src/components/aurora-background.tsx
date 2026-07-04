"use client";

import { useTheme } from "next-themes";
import { useEffect, useRef } from "react";
import * as THREE from "three";

import { cn } from "@/lib/utils";

const VERTEX_SHADER = /* glsl */ `
  void main() {
    gl_Position = vec4(position.xy, 0.0, 1.0);
  }
`;

const FRAGMENT_SHADER = /* glsl */ `
  precision highp float;
  uniform vec2 uResolution;
  uniform float uTime;
  uniform vec3 uColorA;
  uniform vec3 uColorB;
  uniform vec3 uColorC;
  uniform float uIntensity;

  // Simplex noise (Ashima Arts, public domain)
  vec3 mod289(vec3 x) { return x - floor(x * (1.0 / 289.0)) * 289.0; }
  vec2 mod289(vec2 x) { return x - floor(x * (1.0 / 289.0)) * 289.0; }
  vec3 permute(vec3 x) { return mod289(((x * 34.0) + 1.0) * x); }

  float snoise(vec2 v) {
    const vec4 C = vec4(0.211324865405187, 0.366025403784439,
             -0.577350269189626, 0.024390243902439);
    vec2 i  = floor(v + dot(v, C.yy));
    vec2 x0 = v - i + dot(i, C.xx);
    vec2 i1 = (x0.x > x0.y) ? vec2(1.0, 0.0) : vec2(0.0, 1.0);
    vec4 x12 = x0.xyxy + C.xxzz;
    x12.xy -= i1;
    i = mod289(i);
    vec3 p = permute(permute(i.y + vec3(0.0, i1.y, 1.0))
      + i.x + vec3(0.0, i1.x, 1.0));
    vec3 m = max(0.5 - vec3(dot(x0, x0), dot(x12.xy, x12.xy), dot(x12.zw, x12.zw)), 0.0);
    m = m * m;
    m = m * m;
    vec3 x = 2.0 * fract(p * C.www) - 1.0;
    vec3 h = abs(x) - 0.5;
    vec3 ox = floor(x + 0.5);
    vec3 a0 = x - ox;
    m *= 1.79284291400159 - 0.85373472095314 * (a0 * a0 + h * h);
    vec3 g;
    g.x = a0.x * x0.x + h.x * x0.y;
    g.yz = a0.yz * x12.xz + h.yz * x12.yw;
    return 130.0 * dot(m, g);
  }

  void main() {
    vec2 uv = gl_FragCoord.xy / uResolution.xy;
    vec2 p = uv * 2.0 - 1.0;
    p.x *= uResolution.x / uResolution.y;

    float t = uTime * 0.045;
    float n1 = snoise(p * 0.8 + vec2(t, -t));
    float n2 = snoise(p * 1.05 + vec2(-t * 1.3, t * 0.7) + 4.0);
    float n3 = snoise(p * 0.65 + vec2(t * 0.6, t * 1.1) + 8.0);

    // Wide, soft falloff (rather than a hard blob edge) so patches read as a
    // gentle wash instead of a camouflage-like pattern.
    float m1 = smoothstep(-0.6, 1.0, n1);
    float m2 = smoothstep(-0.6, 1.0, n2);
    float m3 = smoothstep(-0.6, 1.0, n3);

    vec3 color = uColorA * m1 * 0.6 + uColorB * m2 * 0.45 + uColorC * m3 * 0.4;
    float alpha = clamp(m1 * 0.32 + m2 * 0.26 + m3 * 0.22, 0.0, 0.9) * uIntensity;
    gl_FragColor = vec4(color * alpha, alpha);
  }
`;

const LIGHT_PALETTE: [string, string, string] = ["#4f46e5", "#06b6d4", "#8b5cf6"];
const DARK_PALETTE: [string, string, string] = ["#818cf8", "#22d3ee", "#a78bfa"];

/** Animated WebGL gradient-mesh background (three.js, fullscreen shader
 * quad). Mounted once per layout (auth screen, app shell) rather than per
 * page, so the render loop and GL context persist across navigation. Bails
 * out to a static single frame under `prefers-reduced-motion` and pauses
 * entirely when the tab isn't visible. */
export function AuroraBackground({
  intensity = 1,
  className,
}: {
  intensity?: number;
  className?: string;
}) {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const { resolvedTheme } = useTheme();
  const paletteRef = useRef<[string, string, string]>(
    resolvedTheme === "dark" ? DARK_PALETTE : LIGHT_PALETTE,
  );

  useEffect(() => {
    paletteRef.current = resolvedTheme === "dark" ? DARK_PALETTE : LIGHT_PALETTE;
  }, [resolvedTheme]);

  useEffect(() => {
    const canvas = canvasRef.current;
    const parent = canvas?.parentElement;
    if (!canvas || !parent) return;

    let renderer: THREE.WebGLRenderer;
    try {
      renderer = new THREE.WebGLRenderer({ canvas, alpha: true, antialias: false });
    } catch {
      return;
    }
    renderer.setPixelRatio(Math.min(window.devicePixelRatio, 1.5));

    const scene = new THREE.Scene();
    const camera = new THREE.OrthographicCamera(-1, 1, 1, -1, 0, 1);

    const uniforms = {
      uResolution: { value: new THREE.Vector2() },
      uTime: { value: 0 },
      uColorA: { value: new THREE.Color(paletteRef.current[0]) },
      uColorB: { value: new THREE.Color(paletteRef.current[1]) },
      uColorC: { value: new THREE.Color(paletteRef.current[2]) },
      uIntensity: { value: intensity },
    };

    const material = new THREE.ShaderMaterial({
      vertexShader: VERTEX_SHADER,
      fragmentShader: FRAGMENT_SHADER,
      uniforms,
      transparent: true,
    });
    const mesh = new THREE.Mesh(new THREE.PlaneGeometry(2, 2), material);
    scene.add(mesh);

    function resize() {
      const width = parent!.clientWidth;
      const height = parent!.clientHeight;
      renderer.setSize(width, height, false);
      uniforms.uResolution.value.set(width, height);
    }
    resize();
    const resizeObserver = new ResizeObserver(resize);
    resizeObserver.observe(parent);

    const reduceMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    const clock = new THREE.Clock();
    let frameId = 0;
    let disposed = false;

    function renderFrame() {
      uniforms.uTime.value = clock.getElapsedTime();
      uniforms.uColorA.value.set(paletteRef.current[0]);
      uniforms.uColorB.value.set(paletteRef.current[1]);
      uniforms.uColorC.value.set(paletteRef.current[2]);
      renderer.render(scene, camera);
    }

    function loop() {
      if (disposed || document.hidden) return;
      renderFrame();
      if (!reduceMotion) frameId = requestAnimationFrame(loop);
    }

    function onVisibilityChange() {
      if (!document.hidden && !disposed) loop();
    }
    document.addEventListener("visibilitychange", onVisibilityChange);

    loop();

    return () => {
      disposed = true;
      cancelAnimationFrame(frameId);
      document.removeEventListener("visibilitychange", onVisibilityChange);
      resizeObserver.disconnect();
      mesh.geometry.dispose();
      material.dispose();
      renderer.dispose();
    };
  }, [intensity]);

  return (
    <canvas
      ref={canvasRef}
      aria-hidden="true"
      className={cn("pointer-events-none absolute inset-0 -z-10 h-full w-full", className)}
    />
  );
}
