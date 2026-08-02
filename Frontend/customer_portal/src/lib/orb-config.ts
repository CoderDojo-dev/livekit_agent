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
  /** intensite du liseré de Fresnel */
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
