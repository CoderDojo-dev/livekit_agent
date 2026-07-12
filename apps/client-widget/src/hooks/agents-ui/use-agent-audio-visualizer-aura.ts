import {
  useCallback,
  useEffect,
  useRef,
  useState,
} from "react";
import type {
  LocalAudioTrack,
  RemoteAudioTrack,
} from "livekit-client";
import {
  animate,
  useMotionValue,
  useMotionValueEvent,
  type AnimationPlaybackControlsWithThen,
  type ValueAnimationTransition,
} from "motion/react";
import {
  useTrackVolume,
  type AgentState,
  type TrackReference,
  type TrackReferenceOrPlaceholder,
} from "@livekit/components-react";

const DEFAULT_SPEED = 10;
const DEFAULT_AMPLITUDE = 2;
const DEFAULT_FREQUENCY = 0.5;
const DEFAULT_SCALE = 0.2;
const DEFAULT_BRIGHTNESS = 1.5;

const REACT_UPDATE_INTERVAL_MS = 1000 / 30;

const DEFAULT_TRANSITION: ValueAnimationTransition = {
  duration: 0.5,
  ease: [0.16, 1, 0.3, 1],
};

const DEFAULT_PULSE_TRANSITION: ValueAnimationTransition = {
  duration: 0.5,
  ease: [0.16, 1, 0.3, 1],
  repeat: Infinity,
  repeatType: "mirror",
};

function useAnimatedValue(initialValue: number) {
  const [value, setValue] = useState(initialValue);
  const motionValue = useMotionValue(initialValue);

  const controlsRef =
    useRef<AnimationPlaybackControlsWithThen | null>(null);
  const frameRef = useRef<number | null>(null);
  const lastCommitRef = useRef(0);
  const pendingValueRef = useRef(initialValue);

  useMotionValueEvent(motionValue, "change", (nextValue) => {
    pendingValueRef.current = nextValue;

    const now = performance.now();
    if (
      frameRef.current !== null ||
      now - lastCommitRef.current < REACT_UPDATE_INTERVAL_MS
    ) {
      return;
    }

    frameRef.current = requestAnimationFrame(() => {
      frameRef.current = null;
      lastCommitRef.current = performance.now();
      setValue(pendingValueRef.current);
    });
  });

  const animateValue = useCallback(
    (
      targetValue: number | number[],
      transition: ValueAnimationTransition,
    ) => {
      controlsRef.current?.stop();
      controlsRef.current = animate(
        motionValue,
        targetValue,
        transition,
      );
    },
    [motionValue],
  );

  useEffect(() => {
    return () => {
      controlsRef.current?.stop();

      if (frameRef.current !== null) {
        cancelAnimationFrame(frameRef.current);
      }
    };
  }, []);

  return {
    value,
    motionValue,
    animate: animateValue,
  };
}

export function useAgentAudioVisualizerAura(
  state: AgentState | undefined,
  audioTrack?:
    | LocalAudioTrack
    | RemoteAudioTrack
    | TrackReferenceOrPlaceholder,
) {
  const [speed, setSpeed] = useState(DEFAULT_SPEED);

  const {
    value: scale,
    animate: animateScale,
    motionValue: scaleMotionValue,
  } = useAnimatedValue(DEFAULT_SCALE);

  const {
    value: amplitude,
    animate: animateAmplitude,
  } = useAnimatedValue(DEFAULT_AMPLITUDE);

  const {
    value: frequency,
    animate: animateFrequency,
  } = useAnimatedValue(DEFAULT_FREQUENCY);

  const {
    value: brightness,
    animate: animateBrightness,
  } = useAnimatedValue(DEFAULT_BRIGHTNESS);

  const volume = useTrackVolume(
    audioTrack as TrackReference,
    {
      fftSize: 256,
      smoothingTimeConstant: 0.7,
    },
  );

  useEffect(() => {
    switch (state) {
      case "idle":
      case "failed":
      case "disconnected":
        setSpeed(10);
        animateScale(0.2, DEFAULT_TRANSITION);
        animateAmplitude(1.2, DEFAULT_TRANSITION);
        animateFrequency(0.4, DEFAULT_TRANSITION);
        animateBrightness(1.0, DEFAULT_TRANSITION);
        return;

      case "listening":
      case "pre-connect-buffering":
        setSpeed(20);
        animateScale(0.3, DEFAULT_TRANSITION);
        animateAmplitude(1.0, DEFAULT_TRANSITION);
        animateFrequency(0.7, DEFAULT_TRANSITION);
        animateBrightness(
          [1.5, 2.0],
          DEFAULT_PULSE_TRANSITION,
        );
        return;

      case "thinking":
      case "connecting":
      case "initializing":
        setSpeed(30);
        animateScale(0.3, DEFAULT_TRANSITION);
        animateAmplitude(0.5, DEFAULT_TRANSITION);
        animateFrequency(1.0, DEFAULT_TRANSITION);
        animateBrightness(
          [0.5, 2.5],
          DEFAULT_PULSE_TRANSITION,
        );
        return;

      case "speaking":
        setSpeed(70);
        animateScale(0.3, DEFAULT_TRANSITION);
        animateAmplitude(0.75, DEFAULT_TRANSITION);
        animateFrequency(1.25, DEFAULT_TRANSITION);
        animateBrightness(1.5, DEFAULT_TRANSITION);
        return;

      default:
        return;
    }
  }, [
    state,
    animateScale,
    animateAmplitude,
    animateFrequency,
    animateBrightness,
  ]);

  useEffect(() => {
    if (
      state !== "speaking" ||
      volume <= 0 ||
      scaleMotionValue.isAnimating()
    ) {
      return;
    }

    animateScale(
      0.2 + 0.2 * volume,
      { duration: 0.06, ease: "linear" },
    );
  }, [
    state,
    volume,
    scaleMotionValue,
    animateScale,
  ]);

  return {
    speed,
    scale,
    amplitude,
    frequency,
    brightness,
  };
}
