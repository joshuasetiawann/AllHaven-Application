import { Cpu, Globe } from "lucide-react";
import { Badge } from "@/components/ui/Badge";

export function PrivacyModeBadge({ external }: { external: boolean }) {
  return external ? (
    <Badge tone="warning">
      <Globe size={11} /> External AI
    </Badge>
  ) : (
    <Badge tone="success">
      <Cpu size={11} /> Local AI Mode
    </Badge>
  );
}
