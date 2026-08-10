# L'Orbe — The Nexus Customer Portal's animated Orb & the Assistant Tab

Everything that makes the glowing orb (its WebGL2 animation, its 9 states, the plinth,
the audio-reactive level) and the full "Assistant" tab (page, shell, rail, tabbar,
navigation, copy, design tokens) work.

---

## 1. File map

| File | Role |
|---|---|
| `src/lib/orb-config.ts` | Orb state machine — 9 states, each a target of uniforms + interpolation duration. Also `ORB_SIZE` (320/240/160) and `ORB_ACTIVE_STATES`. |
| `src/components/orb/orb-renderer.ts` | WebGL2 raymarching renderer — fragment shader (value noise, fbm, 6 structure fields, SDF, Fresnel, halo, dither), render loop, state/level animation. |
| `src/components/orb/orb.tsx` | React component: mounts the renderer on a `<canvas>`, drives `state` and `level`, CSS achromatic fallback when WebGL2 is unavailable. |
| `src/components/orb/orb-plinth.tsx` | The plinth — shadow ellipse + two horizon lines anchoring the orb. |
| `src/routes/_portal/assistant.tsx` | The Assistant tab page: orb stage, scripted conversation state machine, LIVE transcript stream, controls (mute/captions/end), summary card. |
| `src/routes/_portal.tsx` | Layout route: wraps every portal page in `PortalShell`. |
| `src/components/shell/portal-shell.tsx` | Shell: fixed rail + sticky topbar + collapsible left padding, one scroll region. |
| `src/components/shell/portal-rail.tsx` | Desktop navigation: eleven destinations in three groups, collapse button. |
| `src/components/shell/portal-tabbar.tsx` | Mobile bottom tab bar (5 entries, Assistant first) below `lg`. |
| `src/lib/nav.ts` | `NAV` (route data) and `PAGE_HEAD` (topbar titles/subtitles). |
| `src/lib/copy.ts` | Every visible string, incl. the orb's 9 state labels (`copy.assistant.state.*`). |
| `src/lib/fixtures/interactions.ts` | The mock transcript (`SCRIPT`) replayed by the assistant page. |
| `src/styles.css` | Design tokens (13 greys, spacing, motion durations & easings, glow shadows), typography utilities, grain overlay. |

---

## 2. `src/lib/orb-config.ts` — the nine states

Source: `src/lib/orb-config.ts`

```ts
/**
 * lib/orb-config.ts — chapitre 25. La machine a neuf etats de l'Orbe.
 * Chaque etat definit une cible d'uniformes. Le rendu interpole vers la cible.
 */
export type OrbState =
  | "disconnected"
  | "connecting"
  | "preConnect"
  | "initializing"
  | "idle"
  | "listening"
  | "thinking"
  | "speaking"
  | "failed";

export type OrbUniformTarget = {
  /** rayon de la sphere, unites monde */
  radius: number;
  /** luminance de surface, 0..1, achromatique */
  luminance: number;
  /** amplitude du deplacement de bruit */
  noise: number;
  /** frequence du bruit */
  frequency: number;
  /** vitesse d'evolution temporelle */
  speed: number;
  /** intensite du litere de Fresnel */
  rim: number;
  /** mode de champ de structure, 0..5 */
  structure: number;
  /** intensite du champ de structure */
  structureAmount: number;
  /** amplitude de la pulsation spherique */
  pulse: number;
  /** duree d'interpolation vers cet etat, ms */
  transition: number;
};

export const ORB_STATES: Record<OrbState, OrbUniformTarget> = {
  disconnected: {
    radius: 0.82,
    luminance: 0.34,
    noise: 0.045,
    frequency: 1.6,
    speed: 0.08,
    rim: 0.5,
    structure: 0, // Plane
    structureAmount: 0.1,
    pulse: 0.012,
    transition: 640,
  },
  connecting: {
    radius: 0.86,
    luminance: 0.46,
    noise: 0.07,
    frequency: 2.4,
    speed: 0.28,
    rim: 0.66,
    structure: 1, // Ring
    structureAmount: 0.38,
    pulse: 0.03,
    transition: 420,
  },
  preConnect: {
    radius: 0.88,
    luminance: 0.52,
    noise: 0.06,
    frequency: 2.1,
    speed: 0.22,
    rim: 0.72,
    structure: 2, // Bands
    structureAmount: 0.3,
    pulse: 0.026,
    transition: 420,
  },
  initializing: {
    radius: 0.9,
    luminance: 0.58,
    noise: 0.09,
    frequency: 3.1,
    speed: 0.36,
    rim: 0.78,
    structure: 3, // Grid
    structureAmount: 0.44,
    pulse: 0.034,
    transition: 320,
  },
  idle: {
    radius: 0.92,
    luminance: 0.62,
    noise: 0.05,
    frequency: 1.9,
    speed: 0.14,
    rim: 0.8,
    structure: 0, // Plane
    structureAmount: 0.16,
    pulse: 0.02,
    transition: 520,
  },
  listening: {
    radius: 0.98,
    luminance: 0.76,
    noise: 0.12,
    frequency: 2.8,
    speed: 0.42,
    rim: 0.96,
    structure: 1, // Ring
    structureAmount: 0.52,
    pulse: 0.05,
    transition: 240,
  },
  thinking: {
    radius: 0.88,
    luminance: 0.68,
    noise: 0.16,
    frequency: 4.2,
    speed: 0.62,
    rim: 0.86,
    structure: 3, // Grid
    structureAmount: 0.6,
    pulse: 0.018,
    transition: 240,
  },
  speaking: {
    radius: 1.02,
    luminance: 0.88,
    noise: 0.2,
    frequency: 3.4,
    speed: 0.78,
    rim: 1.0,
    structure: 2, // Bands
    structureAmount: 0.66,
    pulse: 0.07,
    transition: 180,
  },
  failed: {
    radius: 0.8,
    luminance: 0.4,
    noise: 0.24,
    frequency: 5.6,
    speed: 0.2,
    rim: 0.44,
    structure: 4, // Cracks
    structureAmount: 0.72,
    pulse: 0.008,
    transition: 320,
  },
};

/** 25.6 geometrie : 320 au repos, 240 en appel, 160 en mobile. */
export const ORB_SIZE = { rest: 320, call: 240, mobile: 160 } as const;

export const ORB_ACTIVE_STATES: readonly OrbState[] = [
  "preConnect",
  "initializing",
  "idle",
  "listening",
  "thinking",
  "speaking",
];
```

---

## 3. `orb-renderer.ts` — the WebGL2 raymarching animation (the core)

File: `src/components/orb/orb-renderer.ts`

```ts
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
  vec3 p = ro;
  for (int i = 0; i < 72; i++) {
    p = ro + rd * d;
    float s = orbSDF(p, t);
    if (s < 0.0012) { hit = 1.0; break; }
    d += s * 0.82;
    if (d > 6.0) break;
  }

  float l = 0.0;

  if (hit > 0.5) {
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

  float alpha = clamp(max(hit, halo * 5.0), 0.0, 1.0);
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

  const dpr = Math.min(typeof window === "undefined" ? 1 : window.devicePixelRatio || 1, 2);

  function resize() {
    const rect = canvas.getBoundingClientRect();
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
```

---

## 4. `orb.tsx` — the React component (mounts the animation)

File: `src/components/orb/orb.tsx`

```tsx
import { useEffect, useRef, useState } from "react";
import { createOrbRenderer, type OrbHandle } from "./orb-renderer";
import { ORB_STATES, type OrbState } from "@/lib/orb-config";
import { cn } from "@/lib/utils";

type OrbProps = {
  state: OrbState;
  /** niveau audio 0..1, pilote l'amplitude du deplacement */
  level?: number;
  size?: number;
  className?: string;
};

/**
 * components/orb/orb.tsx — l'Orbe.
 * Repli CSS cinematique si WebGL2 est indisponible.
 */
export function Orb({ state, level = 0, size = 320, className }: OrbProps) {
  const canvasRef = useRef<HTMLCanvasElement | null>(null);
  const handleRef = useRef<OrbHandle | null>(null);
  const [fallback, setFallback] = useState(false);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const reduced =
      typeof window !== "undefined" &&
      window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    const handle = createOrbRenderer(canvas, state, reduced);
    if (!handle) {
      setFallback(true);
      return;
    }
    handleRef.current = handle;
    return () => {
      handle.destroy();
      handleRef.current = null;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    handleRef.current?.setState(state);
  }, [state]);

  useEffect(() => {
    handleRef.current?.setLevel(level);
  }, [level]);

  const target = ORB_STATES[state];

  return (
    <div
      className={cn("relative select-none", className)}
      style={{ width: size, height: size }}
      aria-hidden="true"
    >
      {fallback ? (
        <div
          className="h-full w-full rounded-[50%] transition-all duration-500"
          style={{
            background: `radial-gradient(circle at 38% 32%, rgba(255,255,255,${
              target.luminance * 0.9
            }) 0%, rgba(255,255,255,${target.luminance * 0.22}) 42%, rgba(255,255,255,0.02) 72%, transparent 100%)`,
            boxShadow: `0 0 ${Math.round(target.rim * 60)}px rgba(255,255,255,${
              target.luminance * 0.14
            })`,
          }}
        />
      ) : (
        <canvas ref={canvasRef} className="h-full w-full" />
      )}
    </div>
  );
}
```

---

## 5. `orb-plinth.tsx` — the shadow / horizon anchoring the orb

File: `src/components/orb/orb-plinth.tsx`

```tsx
import { cn } from "@/lib/utils";

/**
 * components/orb/orb-plinth.tsx — le socle. Une ellipse d'ombre projetee et
 * deux traits d'horizon qui ancrent l'Orbe dans la scene. Chapitre 27.
 */
export function OrbPlinth({ width, className }: { width: number; className?: string }) {
  return (
    <div
      className={cn("pointer-events-none relative", className)}
      style={{ width }}
      aria-hidden="true"
    >
      <div
        className="mx-auto"
        style={{
          width: width * 0.62,
          height: width * 0.09,
          borderRadius: "50%",
          background:
            "radial-gradient(50% 50% at 50% 50%, rgba(0,0,0,0.72) 0%, rgba(0,0,0,0.28) 55%, transparent 100%)",
          filter: "blur(6px)",
        }}
      />
      <div
        className="mx-auto mt-sp-5 h-px"
        style={{
          width: width * 1.15,
          background:
            "linear-gradient(90deg, transparent 0%, var(--stroke-strong) 22%, var(--stroke-strong) 78%, transparent 100%)",
        }}
      />
      <div
        className="mx-auto mt-sp-2 h-px"
        style={{
          width: width * 0.7,
          background:
            "linear-gradient(90deg, transparent 0%, var(--stroke-subtle) 30%, var(--stroke-subtle) 70%, transparent 100%)",
        }}
      />
    </div>
  );
}
```

---

## 6. The tab — `assistant.tsx` (orb scene + live transcript + controls)

File: `src/routes/_portal/assistant.tsx`

```tsx
import { useCallback, useEffect, useRef, useState } from "react";
import { createFileRoute } from "@tanstack/react-router";
import { Mic, MicOff, Captions, Keyboard, Volume2, Lock, Radio } from "lucide-react";
import { Orb } from "@/components/orb/orb";
import { OrbPlinth } from "@/components/orb/orb-plinth";
import { ORB_SIZE, type OrbState } from "@/lib/orb-config";
import { copy } from "@/lib/copy";
import { Button, Card, Divider, IconButton, SectionLabel, StatusChip } from "@/components/portal/primitives";
import { interactions } from "@/lib/fixtures/interactions";
import { cn } from "@/lib/utils";

export const Route = createFileRoute("/_portal/assistant")({
  head: () => ({
    meta: [
      { title: "Assistant — Nexus Customer Portal" },
      {
        name: "description",
        content:
          "Start a private, encrypted voice conversation with the Nexus assistant and see every action it takes on your account.",
      },
      { property: "og:title", content: "Assistant — Nexus Customer Portal" },
      {
        property: "og:description",
        content:
          "Private voice support that confirms before it acts, with a live transcript you can keep.",
      },
    ],
  }),
  component: AssistantScene,
});

type Turn = { speaker: "assistant" | "you"; text: string; at: string };

const SCRIPT: readonly Turn[] = interactions[0]!.transcript.map((t) => ({
  speaker: t.speaker === "specialist" ? "assistant" : t.speaker,
  text: t.text,
  at: t.at,
}));

const ACTIVE: readonly OrbState[] = ["listening", "thinking", "speaking"];

function AssistantScene() {
  const [state, setState] = useState<OrbState>("disconnected");
  const [turns, setTurns] = useState<Turn[]>([]);
  const [ended, setEnded] = useState(false);
  const [muted, setMuted] = useState(false);
  const [captions, setCaptions] = useState(true);
  const [level, setLevel] = useState(0);
  const timers = useRef<ReturnType<typeof setTimeout>[]>([]);

  const clear = useCallback(() => {
    timers.current.forEach(clearTimeout);
    timers.current = [];
  }, []);

  useEffect(() => clear, [clear]);

  useEffect(() => {
    if (!ACTIVE.includes(state)) {
      setLevel(0);
      return;
    }
    const id = setInterval(() => {
      setLevel(state === "thinking" ? 0.2 : 0.25 + Math.random() * 0.65);
    }, 140);
    return () => clearInterval(id);
  }, [state]);

  const at = (ms: number, fn: () => void) => {
    timers.current.push(setTimeout(fn, ms));
  };

  function start() {
    clear();
    setEnded(false);
    setTurns([]);
    setState("connecting");
    at(900, () => setState("preConnect"));
    at(1700, () => setState("initializing"));
    at(2500, () => setState("idle"));
    let t = 3200;
    SCRIPT.forEach((turn, i) => {
      const speaking = turn.speaker === "assistant";
      at(t, () => setState(speaking ? "thinking" : "listening"));
      at(t + (speaking ? 900 : 500), () => {
        if (speaking) setState("speaking");
        setTurns((prev) => [...prev, turn]);
      });
      t += 2600 + turn.text.length * 12;
      if (i === SCRIPT.length - 1) at(t, () => setState("idle"));
    });
  }

  function end() {
    clear();
    setState("disconnected");
    setEnded(true);
  }

  const live = state !== "disconnected";
  const s = copy.assistant.state[state];
  const size = live ? ORB_SIZE.call : ORB_SIZE.rest;

  return (
    <div className="grid gap-sp-9 lg:grid-cols-[minmax(0,1fr)_380px]">
      {/* --- la scene ------------------------------------------------------ */}
      <section className="flex min-h-[560px] flex-col items-center justify-center py-sp-10">
        <div className="flex flex-col items-center">
          <Orb
            state={state}
            level={level}
            size={size}
            className="transition-[width,height] duration-500"
          />
          <OrbPlinth width={size} className="-mt-sp-8" />
        </div>

        <div className="mt-sp-10 max-w-md text-center">
          {!live && !ended ? (
            <h2 className="t-display text-ink-1">{copy.assistant.title}</h2>
          ) : (
            <div className="t-title-2 text-ink-1">{s.label}</div>
          )}
          <p className="t-body mt-sp-4 text-ink-4">{s.detail}</p>
        </div>

        <div className="mt-sp-9 flex items-center gap-sp-5">
          {!live ? (
            <Button variant="primary" size="lg" onClick={start}>
              {copy.assistant.start}
            </Button>
          ) : (
            <>
              <IconButton
                label={muted ? copy.assistant.controls.unmute : copy.assistant.controls.mute}
                onClick={() => setMuted((v) => !v)}
                className={cn(
                  "h-11 w-11 border border-stroke-default bg-surface-2",
                  muted && "bg-surface-4 text-ink-1",
                )}
              >
                {muted ? <MicOff size={17} strokeWidth={1.5} /> : <Mic size={17} strokeWidth={1.5} />}
              </IconButton>
              <IconButton
                label={copy.assistant.controls.captions}
                onClick={() => setCaptions((v) => !v)}
                className={cn(
                  "h-11 w-11 border border-stroke-default bg-surface-2",
                  captions && "bg-surface-4 text-ink-1",
                )}
              >
                <Captions size={17} strokeWidth={1.5} />
              </IconButton>
              <Button variant="danger" size="lg" onClick={end}>
                {copy.assistant.end}
              </Button>
              <IconButton
                label={copy.assistant.controls.volume}
                className="h-11 w-11 border border-stroke-default bg-surface-2"
              >
                <Volume2 size={17} strokeWidth={1.5} />
              </IconButton>
              <IconButton
                label={copy.assistant.controls.keyboard}
                className="h-11 w-11 border border-stroke-default bg-surface-2"
              >
                <Keyboard size={17} strokeWidth={1.5} />
              </IconButton>
            </>
          )}
        </div>

        <div className="t-micro mt-sp-8 flex items-center gap-sp-6 text-ink-5">
          <span className="inline-flex items-center gap-sp-3">
            <Lock size={11} strokeWidth={1.5} />
            {copy.assistant.assurance.encrypted}
          </span>
          <span className="inline-flex items-center gap-sp-3">
            <Radio size={11} strokeWidth={1.5} />
            {copy.assistant.assurance.audioOnly}
          </span>
        </div>
      </section>

      {/* --- le flux ------------------------------------------------------- */}
      <aside className="lg:sticky lg:top-24 lg:self-start">
        {ended ? (
          <Card className="p-sp-7">
            <SectionLabel>{copy.assistant.summary.heading}</SectionLabel>
            <div className="mt-sp-7 grid grid-cols-3 gap-sp-5">
              {[
                [copy.assistant.summary.duration, "4m 18s"],
                [copy.assistant.summary.turns, String(SCRIPT.length)],
                [copy.assistant.summary.actions, "2"],
              ].map(([k, v]) => (
                <div key={k} className="rounded-r-3 border border-stroke-subtle bg-surface-2 p-sp-5">
                  <div className="t-micro-2 text-ink-5">{k}</div>
                  <div className="t-metric-m mt-sp-3 text-ink-1">{v}</div>
                </div>
              ))}
            </div>
            <Divider className="my-sp-7" />
            <div className="t-micro text-ink-4">{copy.assistant.summary.changed}</div>
            <p className="t-body mt-sp-4 text-ink-3">
              {copy.assistant.summary.nothingChanged}
            </p>
            <div className="mt-sp-8 flex gap-sp-4">
              <Button variant="secondary" size="sm">
                {copy.assistant.summary.download}
              </Button>
              <Button variant="quiet" size="sm" onClick={start}>
                {copy.assistant.summary.resume}
              </Button>
            </div>
          </Card>
        ) : (
          <Card className="flex h-[560px] flex-col p-sp-0" inset={false}>
            <div className="flex items-center justify-between border-b border-stroke-subtle px-sp-6 py-sp-5">
              <span className="t-micro text-ink-4">{copy.assistant.stream.heading}</span>
              <StatusChip tone={live ? "solid" : "muted"}>
                {live ? "LIVE" : "IDLE"}
              </StatusChip>
            </div>
            <div className="flex-1 space-y-sp-7 overflow-y-auto px-sp-6 py-sp-6">
              {turns.length === 0 ? (
                <p className="t-caption text-ink-5">
                  {live ? copy.assistant.state.idle.detail : copy.empty.generic}
                </p>
              ) : (
                turns.map((turn, i) => (
                  <div key={i}>
                    <div className="t-micro-2 mb-sp-3 flex items-center gap-sp-4 text-ink-5">
                      <span>
                        {turn.speaker === "assistant"
                          ? copy.assistant.stream.assistant
                          : copy.assistant.stream.you}
                      </span>
                      <span className="t-mono-s">{turn.at}</span>
                    </div>
                    <p
                      className={cn(
                        "t-body",
                        turn.speaker === "assistant" ? "text-ink-1" : "text-ink-3",
                      )}
                    >
                      {turn.text}
                    </p>
                  </div>
                ))
              )}
            </div>
            <div className="border-t border-stroke-subtle p-sp-5">
              <input
                placeholder={copy.assistant.stream.composer}
                className="focus-ring t-ui-regular h-9 w-full rounded-r-2 border border-stroke-default bg-surface-2 px-sp-5 text-ink-1 placeholder:text-ink-5"
              />
            </div>
          </Card>
        )}
      </aside>
    </div>
  );
}
```

---

## 7. The tab plumbing — layout route, shell, rail, tabbar, nav

### `src/routes/_portal.tsx`

```tsx
import { Outlet, createFileRoute } from "@tanstack/react-router";
import { PortalShell } from "@/components/shell/portal-shell";

export const Route = createFileRoute("/_portal")({
  component: PortalLayout,
});

function PortalLayout() {
  return (
    <PortalShell>
      {/* Required: nested routes render here. */}
      <Outlet />
    </PortalShell>
  );
}
```

### `src/components/shell/portal-shell.tsx`

```tsx
import { useState, type ReactNode } from "react";
import { PortalRail } from "./portal-rail";
import { PortalTopbar } from "./portal-topbar";
import { PortalTabbar } from "./portal-tabbar";
import { cn } from "@/lib/utils";

/**
 * components/shell/portal-shell.tsx — chapitre 10.
 * Rail fixe, barre superieure collante, une seule zone de defilement.
 */
export function PortalShell({
  children,
  scene = false,
}: {
  children: ReactNode;
  scene?: boolean;
}) {
  const [collapsed, setCollapsed] = useState(false);

  return (
    <div className="min-h-screen bg-surface-0">
      <PortalRail collapsed={collapsed} onToggle={() => setCollapsed((v) => !v)} />
      <PortalTabbar />
      <div
        className={cn(
          "flex min-h-screen flex-col transition-[padding] duration-300",
          collapsed ? "lg:pl-16" : "lg:pl-64",
        )}
      >
        <PortalTopbar />
        <main
          className={cn(
            "flex-1 pb-20 lg:pb-sp-12",
            scene ? "flex" : "mx-auto w-full max-w-6xl px-sp-8 py-sp-9",
          )}
        >
          {children}
        </main>
      </div>
    </div>
  );
}
```

### `src/components/shell/portal-rail.tsx`

```tsx
import { Link, useRouterState } from "@tanstack/react-router";
import {
  AudioLines,
  History,
  Inbox,
  Layers2,
  ReceiptText,
  LifeBuoy,
  UserRound,
  SlidersHorizontal,
  Shield,
  Info,
  PanelLeft,
  type LucideIcon,
} from "lucide-react";
import { NAV } from "@/lib/nav";
import { copy } from "@/lib/copy";
import { cn } from "@/lib/utils";

const ICONS: Record<string, LucideIcon> = {
  "audio-lines": AudioLines,
  history: History,
  inbox: Inbox,
  "layers-2": Layers2,
  "receipt-text": ReceiptText,
  "life-buoy": LifeBuoy,
  "user-round": UserRound,
  "sliders-horizontal": SlidersHorizontal,
  shield: Shield,
  info: Info,
};

/**
 * components/shell/portal-rail.tsx — chapitre 11.
 * Onze destinations, trois groupes, un pied de marque.
 */
export function PortalRail({
  collapsed,
  onToggle,
}: {
  collapsed: boolean;
  onToggle: () => void;
}) {
  const pathname = useRouterState({ select: (s) => s.location.pathname });

  return (
    <nav
      aria-label="Portal"
      className={cn(
        "fixed inset-y-0 left-0 z-20 hidden shrink-0 flex-col border-r border-stroke-subtle bg-surface-1 transition-[width] duration-300 lg:flex",
        collapsed ? "w-16" : "w-64",
      )}
    >
      <div className="flex h-16 items-center gap-sp-5 border-b border-stroke-subtle px-sp-6">
        <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-r-2 border border-stroke-strong bg-surface-4 shadow-elev-1">
          <span className="t-mono-l text-ink-1">N</span>
        </div>
        {!collapsed && (
          <div className="min-w-0">
            <div className="t-title-3 truncate text-ink-1">{copy.brand.name}</div>
            <div className="t-micro-2 truncate text-ink-5">{copy.brand.version}</div>
          </div>
        )}
      </div>

      <div className="flex-1 overflow-y-auto px-sp-4 py-sp-7">
        {NAV.map((group) => (
          <div key={group.section} className="mb-sp-8 last:mb-0">
            {!collapsed && (
              <div className="t-micro-2 px-sp-4 pb-sp-4 text-ink-5">{group.section}</div>
            )}
            <ul className="space-y-sp-1">
              {group.items.map((item) => {
                const Icon = ICONS[item.icon] ?? Info;
                const active = pathname.startsWith(item.href);
                return (
                  <li key={item.href}>
                    <Link
                      to={item.href}
                      title={collapsed ? item.label : undefined}
                      className={cn(
                        "focus-ring group relative flex h-9 items-center gap-sp-5 rounded-r-2 px-sp-4 transition-colors duration-200",
                        active
                          ? "bg-surface-3 text-ink-1"
                          : "text-ink-4 hover:bg-surface-2 hover:text-ink-2",
                      )}
                    >
                      <span
                        aria-hidden="true"
                        className={cn(
                          "absolute left-0 top-1 h-3 w-px bg-n-12 transition-opacity duration-200",
                          active ? "opacity-100" : "opacity-0",
                        )}
                      />
                      <Icon size={16} strokeWidth={1.5} className="shrink-0" />
                      {!collapsed && <span className="t-ui truncate">{item.label}</span>}
                      {!collapsed && (
                        <span className="t-mono-s ml-auto text-ink-5 opacity-0 transition-opacity duration-200 group-hover:opacity-100">
                          {item.key}
                        </span>
                      )}
                    </Link>
                  </li>
                );
              })}
            </ul>
          </div>
        ))}
      </div>

      <div className="border-t border-stroke-subtle p-sp-4">
        <button
          onClick={onToggle}
          className="focus-ring flex h-9 w-full items-center gap-sp-5 rounded-r-2 px-sp-4 text-ink-4 transition-colors duration-200 hover:bg-surface-2 hover:text-ink-2"
        >
          <PanelLeft size={16} strokeWidth={1.5} className="shrink-0" />
          {!collapsed && (
            <span className="t-label">{copy.shell.collapseRail}</span>
          )}
        </button>
      </div>
    </nav>
  );
}
```

### `src/components/shell/portal-tabbar.tsx` (mobile bottom bar containing the Assistant tab)

```tsx
import { Link, useRouterState } from "@tanstack/react-router";
import { AudioLines, History, Inbox, Layers2, ReceiptText } from "lucide-react";
import { cn } from "@/lib/utils";

const ITEMS = [
  { href: "/assistant", label: "Assistant", Icon: AudioLines },
  { href: "/activity", label: "Activity", Icon: History },
  { href: "/requests", label: "Requests", Icon: Inbox },
  { href: "/services", label: "Services", Icon: Layers2 },
  { href: "/billing", label: "Billing", Icon: ReceiptText },
];

/** 11.9 — en dessous de lg, le rail devient une barre basse de cinq entrees. */
export function PortalTabbar() {
  const pathname = useRouterState({ select: (s) => s.location.pathname });
  return (
    <nav
      aria-label="Portal"
      className="fixed inset-x-0 bottom-0 z-20 flex h-14 border-t border-stroke-subtle bg-surface-1 lg:hidden"
    >
      {ITEMS.map(({ href, label, Icon }) => {
        const active = pathname.startsWith(href);
        return (
          <Link
            key={href}
            to={href}
            className={cn(
              "flex flex-1 flex-col items-center justify-center gap-sp-2 transition-colors duration-200",
              active ? "text-ink-1" : "text-ink-5",
            )}
          >
            <Icon size={17} strokeWidth={1.5} />
            <span className="t-micro-2">{label}</span>
          </Link>
        );
      })}
    </nav>
  );
}
```

---

## 8. Navigation catalogue — `src/lib/nav.ts`

```ts
/**
 * lib/nav.ts — les onze destinations, chapitre 11.2.
 * Aucune douzieme destination.
 */
export type NavItem = {
  href: string;
  label: string;
  icon: string;
  key: string;
};

export type NavSection = {
  section: string;
  items: readonly NavItem[];
};

export const NAV: readonly NavSection[] = [
  {
    section: "ASSISTANT",
    items: [
      { href: "/assistant", label: "Assistant", icon: "audio-lines", key: "G A" },
      { href: "/activity", label: "Activity", icon: "history", key: "G V" },
      { href: "/requests", label: "Requests", icon: "inbox", key: "G R" },
    ],
  },
  {
    section: "ACCOUNT",
    items: [
      { href: "/services", label: "Services", icon: "layers-2", key: "G S" },
      { href: "/billing", label: "Billing", icon: "receipt-text", key: "G B" },
      { href: "/help", label: "Help", icon: "life-buoy", key: "G H" },
    ],
  },
  {
    section: "SETTINGS",
    items: [
      { href: "/profile", label: "Profile", icon: "user-round", key: "G P" },
      { href: "/preferences", label: "Preferences", icon: "sliders-horizontal", key: "G F" },
      { href: "/security", label: "Security", icon: "shield", key: "G K" },
      { href: "/about", label: "About", icon: "info", key: "G I" },
    ],
  },
] as const;

/** Titre et sous-titre de la barre superieure par route, chapitre 12.2. */
export const PAGE_HEAD: Record<string, { title: string; subtitle: string | null }> = {
  "/assistant": { title: "Assistant", subtitle: null },
  "/activity": {
    title: "Activity",
    subtitle: "Everything you and the assistant have done together.",
  },
  "/requests": { title: "Requests", subtitle: "Things we are working on for you." },
  "/services": { title: "Services", subtitle: "What you have with us today." },
  "/billing": {
    title: "Billing",
    subtitle: "Invoices, payment methods, and what is coming next.",
  },
  "/help": { title: "Help", subtitle: "Answers, guides, and a way to reach a person." },
  "/profile": { title: "Profile", subtitle: "Who you are and how we reach you." },
  "/preferences": {
    title: "Preferences",
    subtitle: "How the assistant behaves and how the portal looks.",
  },
  "/security": { title: "Security", subtitle: "Sign-in, devices, and your data." },
  "/about": { title: "About", subtitle: "What the assistant is, and what it is not." },
};
```

---

## 9. Text content feeding the scene — `src/lib/copy.ts` (assistant section)

```ts
export const copy = {
  brand: {
    name: "Nexus",
    tagline: "Voice support that respects your time.",
    version: "Version 1.0.0",
  },
  shell: {
    search: "Search",
    notifications: "Notifications",
    notificationsEmpty: "Nothing new.",
    account: "Account",
    signOut: "Sign out",
    language: "Language",
    collapseRail: "Collapse navigation",
    expandRail: "Expand navigation",
    secure: "SECURE",
  },
  assistant: {
    title: "Private voice support, whenever you need it.",
    start: "Start conversation",
    end: "End",
    assurance: {
      encrypted: "Encrypted end to end",
      audioOnly: "Audio only",
    },
    state: {
      disconnected: {
        label: "Ready when you are",
        detail: "Start a private conversation with the assistant.",
      },
      connecting: {
        label: "Opening a secure line",
        detail: "This usually takes a moment.",
      },
      preConnect: {
        label: "Getting your microphone ready",
        detail: "You can start speaking now.",
      },
      initializing: { label: "The assistant is joining", detail: "Almost there." },
      idle: { label: "Ready to listen", detail: "Speak whenever you are ready." },
      listening: { label: "Listening", detail: "Go ahead." },
      thinking: { label: "Working on it", detail: "Checking your account." },
      speaking: { label: "Speaking", detail: "You can interrupt at any time." },
      failed: {
        label: "Connection needs attention",
        detail: "End the conversation and try again.",
      },
    },
    stream: {
      heading: "LIVE CONVERSATION",
      assistant: "ASSISTANT",
      you: "YOU",
      specialist: "SPECIALIST",
      copyTranscript: "Copy transcript",
      downloadTranscript: "Download as text",
      sentAsText: "Sent as text",
      composer: "Type a message",
    },
    controls: {
      mute: "Mute microphone",
      unmute: "Unmute microphone",
      volume: "Assistant volume",
      captions: "Captions",
      keyboard: "Type instead",
    },
    summary: {
      heading: "CONVERSATION SUMMARY",
      // ... (duration / turns / actions / changed / nothingChanged / download / resume)
    },
  },
};
```

(The full file lives at `src/lib/copy.ts`; the summary block continues after line 70.)

---

## 10. Transcript fixture — `src/lib/fixtures/interactions.ts`

The orb's scripted conversation comes from the first interaction:

```ts
export type InteractionKind = "conversation" | "request" | "callback";

export type Interaction = {
  id: string;
  kind: InteractionKind;
  title: string;
  summary: string;
  at: string;
  relative: string;
  duration: string | null;
  turns: number | null;
  actions: number;
  changed: readonly string[];
  transcript: readonly { speaker: "assistant" | "you" | "specialist"; text: string; at: string }[];
};

export const interactions: readonly Interaction[] = [
  {
    id: "int_2291",
    kind: "conversation",
    title: "Explained the March invoice",
    summary:
      "You asked why March was higher than February. The assistant walked through the two extra call-handling blocks and confirmed nothing was charged twice.",
    at: "Today, 09:12",
    relative: "2 hours ago",
    duration: "4m 18s",
    turns: 14,
    actions: 2,
    changed: [],
    transcript: [
      { speaker: "you", text: "Why is March higher than February?", at: "00:04" },
      {
        speaker: "assistant",
        text: "March includes two extra call-handling blocks that were added on 8 March. Each block is £6.00, so the total is £12.00 above your usual amount.",
        at: "00:09",
      },
      { speaker: "you", text: "Was anything charged twice?", at: "00:31" },
      {
        speaker: "assistant",
        text: "No. I checked every line on the invoice and each charge appears once.",
        at: "00:35",
      },
    ],
  },
  // ... more interactions
];
```

---

## 11. Design tokens & motion (from `src/styles.css`)

These are the variables the whole look depends on — greys, surfaces, strokes, motion durations/easings, grain overlay:

```css
@import "tailwindcss" source(none);
@source "../src";

:root {
  /* -- Chapitre 2.1 : les treize valeurs -- */
  --n-0: #000000;
  --n-1: #0a0a0a;
  --n-2: #101010;
  --n-3: #141414;
  --n-4: #1a1a1a;
  --n-5: #212121;
  --n-6: #2a2a2a;
  --n-7: #383838;
  --n-8: #4d4d4d;
  --n-9: #6e6e6e;
  --n-10: #9b9b9b;
  --n-11: #c9c9c9;
  --n-12: #ffffff;

  --surface-0: var(--n-1);
  --surface-1: var(--n-2);
  --surface-2: var(--n-3);
  --surface-3: var(--n-4);
  --surface-4: var(--n-5);
  --surface-5: var(--n-6);

  --stroke-subtle: rgba(255, 255, 255, 0.06);
  --stroke-default: rgba(255, 255, 255, 0.09);
  --stroke-strong: rgba(255, 255, 255, 0.14);
  --stroke-ink: rgba(255, 255, 255, 0.24);

  --ink-1: var(--n-12);
  --ink-2: var(--n-11);
  --ink-3: var(--n-10);
  --ink-4: var(--n-9);
  --ink-5: var(--n-8);
  --ink-inverse: var(--n-0);

  --sp-1: 2px;  --sp-2: 4px;  --sp-3: 6px;  --sp-4: 8px;
  --sp-5: 12px; --sp-6: 16px; --sp-7: 20px; --sp-8: 24px;
  --sp-9: 32px; --sp-10: 40px; --sp-11: 56px; --sp-12: 80px;

  --r-0: 0px; --r-1: 4px; --r-2: 6px; --r-3: 8px; --r-4: 10px; --r-5: 12px;

  /* elevations */
  --elev-0: inset 0 1px 0 rgba(255, 255, 255, 0.04);
  --elev-1: inset 0 1px 0 rgba(255, 255, 255, 0.05), 0 1px 2px rgba(0, 0, 0, 0.4);
  --elev-2: inset 0 1px 0 rgba(255, 255, 255, 0.07), 0 4px 10px -2px rgba(0, 0, 0, 0.5);
  --elev-3: inset 0 1px 0 rgba(255, 255, 255, 0.08), 0 12px 24px -6px rgba(0, 0, 0, 0.6), 0 2px 6px -2px rgba(0, 0, 0, 0.4);
  --elev-4: inset 0 1px 0 rgba(255, 255, 255, 0.09), 0 32px 64px -12px rgba(0, 0, 0, 0.7), 0 8px 20px -6px rgba(0, 0, 0, 0.5);

  /* glow */
  --glow-soft: 0 0 24px rgba(255, 255, 255, 0.06);
  --glow-strong: 0 0 48px rgba(255, 255, 255, 0.1);
  --glow-line: 0 0 12px rgba(255, 255, 255, 0.14);

  /* z-layers */
  --z-base: 0; --z-sticky: 10; --z-rail: 20; --z-topbar: 30; --z-callbar: 40;
  --z-dropdown: 50; --z-popover: 60; --z-tooltip: 70; --z-overlay: 80; --z-drawer: 90;
  --z-dialog: 100; --z-command: 110; --z-toast: 120; --z-grain: 9999;

  /* motion */
  --d-1: 80ms; --d-2: 120ms; --d-3: 180ms; --d-4: 240ms;
  --d-5: 320ms; --d-6: 420ms; --d-7: 520ms; --d-8: 640ms; --d-9: 900ms;
  --ease-out: cubic-bezier(0.22, 1, 0.36, 1);
  --ease-in: cubic-bezier(0.4, 0, 1, 1);
  --ease-out-soft: cubic-bezier(0.33, 1, 0.68, 1);
  --ease-in-out: cubic-bezier(0.65, 0, 0.35, 1);
}

/* grain overlay — kills banding, fixed above everything */
body::after {
  content: "";
  position: fixed;
  inset: 0;
  z-index: var(--z-grain);
  pointer-events: none;
  background-image: url("/noise.png");
  background-size: 160px 160px;
  background-repeat: repeat;
  opacity: 0.028;
  mix-blend-mode: overlay;
}

@media (prefers-reduced-motion: reduce) {
  *,
  *::before,
  *::after {
    animation-duration: 0.001ms !important;
    animation-iteration-count: 1 !important;
    transition-duration: 0.001ms !important;
  }
}
```

Typographic utilities used by the scene (`t-display`, `t-title-2`, `t-body`, `t-micro`,
`t-micro-2`, `t-mono-s`, `t-metric-m`, `t-ui-regular`, `t-caption`) are defined as
`@utility` blocks in the same `styles.css` (section 4.3, eighteen tokens).

---

## 12. Data flow / how the animation actually happens

1. **The user lands on `/assistant`** → route `src/routes/_portal/assistant.tsx` → `AssistantScene`.
2. **`Orb` mounts** → `useEffect` calls `createOrbRenderer(canvas, "disconnected", reducedMotion)` in `orb-renderer.ts`, which sets up WebGL2, compiles the vertex + fragment shaders, and starts a `requestAnimationFrame` loop.
3. **Every frame** the renderer:
   - resizes the canvas to devicePixelRatio, clamped to 2;
   - lerps each uniform from `current` toward `target` with `k = 1 - exp(-dt*1000*3 / transition)` (the state transition duration from `orb-config.ts`);
   - lerps the audio `level` toward `levelTarget` at `dt * 12`;
   - raymarches the SDF sphere (72 steps), applies fbm noise displacement modulated by `u_level`, the structure field mode, Lambert+wrap+specular+Fresnel lighting, an achromatic outer halo, and a dither to kill banding; renders `vec4(vec3(l), alpha)`.
4. **User clicks "Start conversation"** → `start()` fires `setTimeout` chain: `connecting` (0 ms) → `preConnect` (900) → `initializing` (1700) → `idle` (2500), then per transcript turn `thinking|listening` → `speaking`, each pushed into `turns` for the LIVE card.
5. **`level` jitter** while in `ACTIVE` states: every 140 ms `level = 0.25 + random*0.65` (0.2 when thinking) — this drives the `u_level` displacement and pulse amplitude, making the orb vibrate as if listening/speaking.
6. **`OrbPlinth`** renders the shadow ellipse + two horizon strokes anchored under the orb; the orb sizeswitch `rest 320px` → `call 240px` (live) is animated with `transition-[width,height] duration-500`.
7. **Tab itself** is routed under `/_portal.tsx` (layout), shell = fixed rail + sticky topbar + mobile tabbar; `nav.ts` registers `/assistant` as the first destination in both rail and mobile tabbar.

---

## 7. How to run it

```sh
cd Frontend/customer_portal
npm install
npm run dev
# open http://localhost:8080/ → Assistant (rail or url /assistant)
```

Requires Node.js ≥ 20 (Node 24 works), no GPU requirement beyond WebGL2 browser support
(fallback: achromatic CSS radial gradient).