import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Progress } from "@/components/ui/progress";
import { Flame, Droplet, Wind, CloudRain } from "lucide-react";

interface RiskScoreCardProps {
  riskType: string;
  score: number;
  explanation: string;
}

const getRiskIcon = (type: string) => {
  switch (type.toLowerCase()) {
    case "flood":
      return Droplet;
    case "wildfire":
      return Flame;
    case "storm":
      return Wind;
    case "drought":
      return CloudRain;
    default:
      return Droplet;
  }
};

const getRiskLevel = (score: number) => {
  if (score < 30) return { label: "Low", color: "success" };
  if (score < 70) return { label: "Moderate", color: "warning" };
  return { label: "High", color: "danger" };
};

const getRiskColorClass = (score: number) => {
  if (score < 30) return "text-success";
  if (score < 70) return "text-warning";
  return "text-danger";
};

const getProgressColorClass = (score: number) => {
  if (score < 30) return "[&>div]:bg-success";
  if (score < 70) return "[&>div]:bg-warning";
  return "[&>div]:bg-danger";
};

export const RiskScoreCard = ({ riskType, score, explanation }: RiskScoreCardProps) => {
  const Icon = getRiskIcon(riskType);
  const riskLevel = getRiskLevel(score);

  return (
    <Card className="transition-all hover:shadow-lg">
      <CardHeader>
        <CardTitle className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <Icon className={`h-5 w-5 ${getRiskColorClass(score)}`} />
            <span>{riskType}</span>
          </div>
          <span className={`text-2xl font-bold ${getRiskColorClass(score)}`}>
            {score}%
          </span>
        </CardTitle>
      </CardHeader>
      <CardContent className="space-y-4">
        <div className="space-y-2">
          <div className="flex justify-between text-sm">
            <span className="text-muted-foreground">Risk Level</span>
            <span className={`font-semibold ${getRiskColorClass(score)}`}>
              {riskLevel.label}
            </span>
          </div>
          <Progress value={score} className={getProgressColorClass(score)} />
        </div>
        <p className="text-sm text-muted-foreground leading-relaxed">
          {explanation}
        </p>
      </CardContent>
    </Card>
  );
};

