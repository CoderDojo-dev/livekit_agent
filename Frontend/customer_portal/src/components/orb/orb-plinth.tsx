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
