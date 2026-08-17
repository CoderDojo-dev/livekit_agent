import type { ComponentProps } from "react";
import { useEnsureRoom, useStartAudio } from "@livekit/components-react";
import { Button } from "@/components/portal/primitives";
import { Room } from "livekit-client";

/**
 * Port of apps/client-widget/src/components/agents-ui/start-audio-button.tsx:
 * browsers block autoplay until a gesture, so this button enables audio on
 * demand. Only renders while audio playback is blocked.
 */
export interface StartAudioButtonProps extends ComponentProps<"button"> {
  /** The LiveKit room instance. If not provided, uses the room from context. */
  room?: Room;
  /** The label text to display on the button. */
  label: string;
}

export function StartAudioButton({ label, room, ...props }: StartAudioButtonProps) {
  const roomEnsured = useEnsureRoom(room);
  const { mergedProps } = useStartAudio({ room: roomEnsured, props });

  return (
    <Button variant="secondary" size="sm" {...props} {...mergedProps}>
      {label}
    </Button>
  );
}
