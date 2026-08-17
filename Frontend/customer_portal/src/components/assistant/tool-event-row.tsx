import { motion } from "motion/react";
import {
  Check,
  CircleAlert,
  CreditCard,
  Headset,
  Search,
  ShieldCheck,
  SignalHigh,
  UserRound,
} from "lucide-react";
import { toolKind, type ToolKind } from "@/lib/tool-events";
import { T_MICRO } from "@/components/portal/data";
import { cn } from "@/lib/utils";
import { copy } from "@/lib/copy";

const ICON: Record<ToolKind, typeof Search> = {
  account: UserRound,
  billing: CreditCard,
  network: SignalHigh,
  support: Headset,
  security: ShieldCheck,
  other: Search,
};

/**
 * One completed service action.
 *
 * Deliberately quieter than a transcript bubble: it is context, not speech.
 * A failure is marked with a neutral alert glyph and muted ink — there is no
 * red anywhere in the palette (13 greys), and inventing one would break the
 * identity.
 */
export function ToolEventRow({
  name,
  text,
  status,
}: {
  name: string;
  text: string;
  status: "done" | "error";
}) {
  const Icon = ICON[toolKind(name)];
  const failed = status === "error";

  return (
    <div className="flex items-center gap-sp-5">
      <span
        aria-hidden="true"
        className={cn(
          "flex h-7 w-7 shrink-0 items-center justify-center rounded-r-2 border",
          failed
            ? "border-dashed border-stroke-strong bg-surface-2 text-ink-4"
            : "border-stroke-subtle bg-surface-3 text-ink-3",
        )}
      >
        <Icon size={14} strokeWidth={1.5} />
      </span>

      <div className="min-w-0 flex-1">
        <div className="t-micro-2 text-ink-5">{copy.assistant.tools.heading}</div>
        <p dir="auto" className={cn("t-ui mt-sp-1 truncate", failed ? "text-ink-3" : "text-ink-2")}>
          {text}
        </p>
      </div>

      <motion.span
        initial={{ opacity: 0, scale: 0.8 }}
        animate={{ opacity: 1, scale: 1 }}
        transition={T_MICRO}
        aria-label={failed ? copy.assistant.tools.failed : copy.assistant.tools.done}
        className={cn("shrink-0", failed ? "text-ink-4" : "text-ink-2")}
      >
        {failed ? (
          <CircleAlert size={14} strokeWidth={1.5} />
        ) : (
          <Check size={14} strokeWidth={1.5} />
        )}
      </motion.span>
    </div>
  );
}
