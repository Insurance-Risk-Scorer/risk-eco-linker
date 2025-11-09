import { CheckCircle, XCircle, AlertTriangle } from "lucide-react";
import { Badge } from "@/components/ui/badge";

interface DecisionBadgeProps {
  decision: string;
}

const getDecisionConfig = (decision: string) => {
  const normalized = decision.toUpperCase();
  
  if (normalized.includes("APPROVE")) {
    return {
      icon: CheckCircle,
      label: "Approved",
      variant: "success" as const,
    };
  }
  
  if (normalized.includes("DENY")) {
    return {
      icon: XCircle,
      label: "Denied",
      variant: "danger" as const,
    };
  }
  
  return {
    icon: AlertTriangle,
    label: "Flag for Review",
    variant: "warning" as const,
  };
};

export const DecisionBadge = ({ decision }: DecisionBadgeProps) => {
  const config = getDecisionConfig(decision);
  const Icon = config.icon;

  return (
    <Badge 
      variant={config.variant}
      className="text-base px-4 py-2 gap-2"
    >
      <Icon className="h-4 w-4" />
      {config.label}
    </Badge>
  );
};

