/**
 * components/orb/orb-renderer.ts — WebGL2 raymarching, chapitre 26.
 * Strictement achromatique : la couleur finale est vec3(l), donc R === G === B.
 */
import { ORB_STATES, type OrbState, type OrbUniformTarget } from "@/lib/orb-config";

const VERT = `#version 300 es
in vec2 a_pos;
void main() { gl_Position = vec4(a_pos, 0.0, 1.0); }
`;

const FRAG = `#version 300 es
precision highp float;

out vec4 fragColor;

uniform vec2  u_res;
uniform float u_time;
uniform float u_radius;
uniform float u_lum;
uniform float u_noise;
uniform float u_freq;
uniform float u_speed;
uniform float u_rim;
uniform float u_structure;
uniform float u_structureAmount;
uniform float u_pulse;
uniform float u_level;
uniform float u_dpr;

// ---- bruit de valeur 3D ----------------------------------------------------
float hash(vec3 p) {
  p = fract(p * 0.3183099 + vec3(0.1, 0.2, 0.3));
  p *= 17.0;
  return fract(p.x * p.y * p.z * (p.x + p.y + p.z));
}

float vnoise(vec3 x) {
  vec3 i = floor(x);
  vec3 f = fract(x);
  f = f * f * (3.0 - 2.0 * f);
  return mix(
    mix(mix(hash(i + vec3(0,0,0)), hash(i + vec3(1,0,0)), f.x),
        mix(hash(i + vec3(0,1,0)), hash(i + vec3(1,1,0)), f.x), f.y),
    mix(mix(hash(i + vec3(0,0,1)), hash(i + vec3(1,0,1)), f.x),
        mix(hash(i + vec3(0,1,1)), hash(i + vec3(1,1,1)), f.x), f.y),
    f.z);
}

float fbm(vec3 p) {
  float a = 0.5;
  float s = 0.0;
  for (int i = 0; i < 4; i++) {
    s += a * vnoise(p);
    p *= 2.02;
    a *= 0.5;
  }
  return s;
}

// ---- pulsation spherique ---------------------------------------------------
float sphericalPulse(vec3 p, float t) {
  float lat = asin(clamp(p.y / max(length(p), 1e-4), -1.0, 1.0));
  float lon = atan(p.z, p.x);
  float a = sin(lat * 3.0 - t * 1.2);
  float b = sin(lon * 2.0 + t * 0.9);
  return (a * b) * 0.5;
}

// ---- champ de structure : six modes ---------------------------------------
// 0 Plane, 1 Ring, 2 Bands, 3 Grid, 4 Cracks, 5 Dust
float structureField(vec3 p, float mode, float t) {
  float m = floor(mode + 0.5);
  if (m < 0.5) {
    // Plane : une nappe horizontale lente
    return smoothstep(0.30, 0.0, abs(p.y - sin(t * 0.25) * 0.12));
  } else if (m < 1.5) {
    // Ring : un anneau equatorial qui respire
    float r = length(p.xz);
    return smoothstep(0.16, 0.0, abs(r - (0.62 + sin(t * 1.4) * 0.05))) *
           smoothstep(0.45, 0.0, abs(p.y));
  } else if (m < 2.5) {
    // Bands : bandes latitudinales en defilement
    return 0.5 + 0.5 * sin(p.y * 16.0 - t * 2.6);
  } else if (m < 3.5) {
    // Grid : maille meridiens x paralleles
    float lon = atan(p.z, p.x);
    float lat = asin(clamp(p.y, -1.0, 1.0));
    float a = 0.5 + 0.5 * sin(lon * 12.0 + t * 1.1);
    float b = 0.5 + 0.5 * sin(lat * 12.0 - t * 0.7);
    return max(pow(a, 6.0), pow(b, 6.0));
  } else if (m < 4.5) {
    // Cracks : fractures anguleuses, reservees a l'echec
    float n = fbm(p * 4.0 + t * 0.15);
    return smoothstep(0.02, 0.0, abs(n - 0.5)) * 1.4;
  }
  // Dust : granulation fine et instable
  return step(0.86, fract(hash(floor(p * 60.0)) + t * 0.35));
}

// ---- SDF de l'orbe ---------------------------------------------------------
float orbSDF(vec3 p, float t) {
  float base = length(p) - u_radius;
  float pulse = sphericalPulse(p, t) * u_pulse * (1.0 + u_level);
  float n = (fbm(p * u_freq + vec3(0.0, 0.0, t * u_speed)) - 0.5) * 2.0;
  float disp = n * u_noise * (0.65 + u_level * 0.9);
  float s = structureField(normalize(p + 1e-5), u_structure, t) * u_structureAmount * 0.045;
  return base + pulse + disp - s;
}

vec3 orbNormal(vec3 p, float t) {
  vec2 e = vec2(0.0018, 0.0);
  return normalize(vec3(
    orbSDF(p + e.xyy, t) - orbSDF(p - e.xyy, t),
    orbSDF(p + e.yxy, t) - orbSDF(p - e.yxy, t),
    orbSDF(p + e.yyx, t) - orbSDF(p - e.yyx, t)
  ));
}

void main() {
  vec2 uv = (gl_FragCoord.xy * 2.0 - u_res) / min(u_res.x, u_res.y);
  float t = u_time;

  vec3 ro = vec3(0.0, 0.0, 3.0);
  vec3 rd = normalize(vec3(uv, -1.85));

  float d = 0.0;
  float hit = 0.0;
  float closest = 1e9;
  vec3 pClosest = ro;
  vec3 p = ro;
  for (int i = 0; i < 96; i++) {
    p = ro + rd * d;
    float s = orbSDF(p, t);
    if (s < closest) { closest = s; pClosest = p; }
    if (s < 0.0012) { hit = 1.0; break; }
    d += s * 0.82;
    if (d > 6.0) break;
  }

  // Couverture anti-aliasee : feathering sur ~1.5 pixel en espace uv.
  float px = 2.0 / min(u_res.x, u_res.y);
  float cov = hit > 0.5 ? 1.0 : 1.0 - smoothstep(0.0, px * 1.5, closest);

  float l = 0.0;

  if (cov > 0.004) {
    p = (hit > 0.5) ? p : pClosest;
    vec3 n = orbNormal(p, t);
    vec3 v = normalize(ro - p);
    vec3 key = normalize(vec3(-0.45, 0.75, 0.55));

    float lambert = max(dot(n, key), 0.0);
    float wrap = max(dot(n, normalize(vec3(0.6, -0.3, 0.4))), 0.0) * 0.18;
    float spec = pow(max(dot(reflect(-key, n), v), 0.0), 46.0) * 0.35;
    float fres = pow(1.0 - max(dot(n, v), 0.0), 2.6) * u_rim;

    float surf = structureField(n, u_structure, t) * u_structureAmount * 0.28;
    float grain = (fbm(n * 9.0 + t * 0.2) - 0.5) * 0.06;

    l = u_lum * (0.14 + lambert * 0.72) + wrap + spec + fres * 0.42 + surf + grain;
    l *= smoothstep(0.0, 0.06, 1.0 - length(uv) * 0.34);
  }

  // halo exterieur, achromatique
  float halo = exp(-max(length(uv) - u_radius, 0.0) * 6.2) * u_lum * 0.16;
  l += halo * (1.0 - hit * 0.55);

  // tramage pour casser le banding sur les degrades sombres
  float dither = (fract(sin(dot(gl_FragCoord.xy, vec2(12.9898, 78.233))) * 43758.5453) - 0.5) / 255.0;
  l = clamp(l + dither, 0.0, 1.0);

  float alpha = clamp(max(cov, halo * 5.0), 0.0, 1.0);
  fragColor = vec4(vec3(l), alpha);
}
`;

const UNIFORM_KEYS = [
  "radius",
  "luminance",
  "noise",
  "frequency",
  "speed",
  "rim",
  "structure",
  "structureAmount",
  "pulse",
] as const;

type UniformKey = (typeof UNIFORM_KEYS)[number];
type Values = Record<UniformKey, number>;

function valuesOf(target: OrbUniformTarget): Values {
  return {
    radius: target.radius,
    luminance: target.luminance,
    noise: target.noise,
    frequency: target.frequency,
    speed: target.speed,
    rim: target.rim,
    structure: target.structure,
    structureAmount: target.structureAmount,
    pulse: target.pulse,
  };
}

function compile(gl: WebGL2RenderingContext, type: number, src: string) {
  const sh = gl.createShader(type)!;
  gl.shaderSource(sh, src);
  gl.compileShader(sh);
  if (!gl.getShaderParameter(sh, gl.COMPILE_STATUS)) {
    const log = gl.getShaderInfoLog(sh);
    gl.deleteShader(sh);
    throw new Error(log ?? "shader compile failed");
  }
  return sh;
}

export type OrbHandle = {
  setState: (state: OrbState) => void;
  setLevel: (level: number) => void;
  destroy: () => void;
};

export function createOrbRenderer(
  canvas: HTMLCanvasElement,
  initial: OrbState,
  reducedMotion: boolean,
): OrbHandle | null {
  const gl = canvas.getContext("webgl2", {
    alpha: true,
    antialias: false,
    premultipliedAlpha: false,
    powerPreference: "low-power",
  });
  if (!gl) return null;

  let program: WebGLProgram;
  try {
    const vs = compile(gl, gl.VERTEX_SHADER, VERT);
    const fs = compile(gl, gl.FRAGMENT_SHADER, FRAG);
    program = gl.createProgram()!;
    gl.attachShader(program, vs);
    gl.attachShader(program, fs);
    gl.linkProgram(program);
    if (!gl.getProgramParameter(program, gl.LINK_STATUS)) {
      throw new Error(gl.getProgramInfoLog(program) ?? "link failed");
    }
  } catch {
    return null;
  }

  const buf = gl.createBuffer();
  gl.bindBuffer(gl.ARRAY_BUFFER, buf);
  gl.bufferData(
    gl.ARRAY_BUFFER,
    new Float32Array([-1, -1, 3, -1, -1, 3]),
    gl.STATIC_DRAW,
  );
  const loc = gl.getAttribLocation(program, "a_pos");
  gl.enableVertexAttribArray(loc);
  gl.vertexAttribPointer(loc, 2, gl.FLOAT, false, 0, 0);

  const u = {
    res: gl.getUniformLocation(program, "u_res"),
    time: gl.getUniformLocation(program, "u_time"),
    radius: gl.getUniformLocation(program, "u_radius"),
    lum: gl.getUniformLocation(program, "u_lum"),
    noise: gl.getUniformLocation(program, "u_noise"),
    freq: gl.getUniformLocation(program, "u_freq"),
    speed: gl.getUniformLocation(program, "u_speed"),
    rim: gl.getUniformLocation(program, "u_rim"),
    structure: gl.getUniformLocation(program, "u_structure"),
    structureAmount: gl.getUniformLocation(program, "u_structureAmount"),
    pulse: gl.getUniformLocation(program, "u_pulse"),
    level: gl.getUniformLocation(program, "u_level"),
    dpr: gl.getUniformLocation(program, "u_dpr"),
  };

  let current = valuesOf(ORB_STATES[initial]);
  let target = { ...current };
  let transition = ORB_STATES[initial].transition;
  let level = 0;
  let levelTarget = 0;
  let raf = 0;
  let disposed = false;
  const start = performance.now();
  let last = start;

  // Budget fixe de fragments : jamais plus cher que le pire cas actuel
  // (orbe 320 px @ DPR 2 = 640x640). Les petits canvas gagnent du DPR natif.
  const FRAGMENT_BUDGET = 640 * 640;
  let dpr = 1;

  function effectiveDpr(rect: DOMRect) {
    const device = typeof window === "undefined" ? 1 : window.devicePixelRatio || 1;
    const area = Math.max(rect.width * rect.height, 1);
    return Math.max(1, Math.min(device, Math.sqrt(FRAGMENT_BUDGET / area), 3));
  }

  function resize() {
    const rect = canvas.getBoundingClientRect();
    dpr = effectiveDpr(rect);
    const w = Math.max(1, Math.round(rect.width * dpr));
    const h = Math.max(1, Math.round(rect.height * dpr));
    if (canvas.width !== w || canvas.height !== h) {
      canvas.width = w;
      canvas.height = h;
    }
    gl!.viewport(0, 0, canvas.width, canvas.height);
  }

  function frame(now: number) {
    if (disposed) return;
    const dt = Math.min((now - last) / 1000, 0.05);
    last = now;
    resize();

    const k = 1 - Math.exp((-dt * 1000 * 3) / Math.max(transition, 1));
    for (const key of UNIFORM_KEYS) {
      current[key] += (target[key] - current[key]) * k;
    }
    level += (levelTarget - level) * Math.min(dt * 12, 1);

    gl!.useProgram(program);
    gl!.uniform2f(u.res, canvas.width, canvas.height);
    gl!.uniform1f(u.time, reducedMotion ? 0 : (now - start) / 1000);
    gl!.uniform1f(u.radius, current.radius);
    gl!.uniform1f(u.lum, current.luminance);
    gl!.uniform1f(u.noise, current.noise);
    gl!.uniform1f(u.freq, current.frequency);
    gl!.uniform1f(u.speed, current.speed);
    gl!.uniform1f(u.rim, current.rim);
    gl!.uniform1f(u.structure, current.structure);
    gl!.uniform1f(u.structureAmount, current.structureAmount);
    gl!.uniform1f(u.pulse, current.pulse);
    gl!.uniform1f(u.level, level);
    gl!.uniform1f(u.dpr, dpr);

    gl!.clearColor(0, 0, 0, 0);
    gl!.clear(gl!.COLOR_BUFFER_BIT);
    gl!.enable(gl!.BLEND);
    gl!.blendFunc(gl!.SRC_ALPHA, gl!.ONE_MINUS_SRC_ALPHA);
    gl!.drawArrays(gl!.TRIANGLES, 0, 3);

    raf = requestAnimationFrame(frame);
  }

  raf = requestAnimationFrame(frame);

  return {
    setState(state: OrbState) {
      const next = ORB_STATES[state];
      target = valuesOf(next);
      transition = next.transition;
    },
    setLevel(v: number) {
      levelTarget = Math.max(0, Math.min(1, v));
    },
    destroy() {
      disposed = true;
      cancelAnimationFrame(raf);
      gl.deleteBuffer(buf);
      gl.deleteProgram(program);
    },
  };
}
