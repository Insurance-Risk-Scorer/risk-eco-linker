import { useState } from "react";
import { AddressInput } from "@/components/AddressInput";
import { RiskScoreCard } from "@/components/RiskScoreCard";
import { DecisionBadge } from "@/components/DecisionBadge";
import { LocationDataCard } from "@/components/LocationDataCard";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { Shield, MapPin, AlertCircle } from "lucide-react";
import { useToast } from "@/hooks/use-toast";

interface RiskScore {
  risk_type: string;
  score: number;
  explanation: string;
}

interface RiskReport {
  location: {
    address: string;
    latitude: number;
    longitude: number;
  };
  risk_scores: RiskScore[];
  overall_summary: string;
  automated_decision: string;
  location_data?: any; // Optional Earth Engine location data
}

const Index = () => {
  const [isLoading, setIsLoading] = useState(false);
  const [report, setReport] = useState<RiskReport | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [formResetKey, setFormResetKey] = useState(0);
  const [mapboxToken, setMapboxToken] = useState(() => {
    // First try to get from environment variable (VITE_MAPBOX_API_KEY)
    const envToken = import.meta.env.VITE_MAPBOX_API_KEY || "";
    // Fallback to localStorage if env variable is not set
    return envToken || localStorage.getItem("mapbox_token") || "";
  });
  const { toast } = useToast();

  const handleTokenChange = (token: string) => {
    setMapboxToken(token);
    // Only save to localStorage if not using env variable
    if (!import.meta.env.VITE_MAPBOX_API_KEY) {
      localStorage.setItem("mapbox_token", token);
    }
  };

  const handleAddressSubmit = async (address: string, coordinates: { lat: number; lng: number } | null) => {
    setIsLoading(true);
    setError(null);
    setReport(null);

    try {
      // Use environment variable for API URL, fallback to localhost for development
      const apiUrl = import.meta.env.VITE_API_URL || "http://localhost:5001";
      
      // Build request body - include coordinates only if available
      const requestBody: { address: string; latitude?: number; longitude?: number } = { address };
      if (coordinates) {
        requestBody.latitude = coordinates.lat;
        requestBody.longitude = coordinates.lng;
      }
      
      const response = await fetch(`${apiUrl}/api/get-risk-report`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify(requestBody),
      });

      if (!response.ok) {
        throw new Error(`API error: ${response.status}`);
      }

      const data = await response.json();
      setReport(data);
      
      // Reset the form for the next address
      setFormResetKey(prev => prev + 1);
      
      toast({
        title: "Risk Assessment Complete",
        description: "Property risk analysis has been generated successfully.",
      });
    } catch (err) {
      const errorMessage = err instanceof Error ? err.message : "Failed to fetch risk assessment";
      setError(errorMessage);
      
      toast({
        title: "Error",
        description: errorMessage,
        variant: "destructive",
      });
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="min-h-screen bg-background">
      {/* Header */}
      <header className="border-b bg-card">
        <div className="container mx-auto px-4 py-6">
          <div className="flex items-center gap-3">
            <Shield className="h-8 w-8 text-primary" />
            <div>
              <h1 className="text-2xl font-bold text-foreground">AlphaEarth Insurance</h1>
              <p className="text-sm text-muted-foreground">AI-Powered Risk Assessment Platform</p>
            </div>
          </div>
        </div>
      </header>

      {/* Main Content */}
      <main className="container mx-auto px-4 py-12">
        <div className="space-y-8">
          {/* Input Section */}
          <div className="flex flex-col items-center space-y-4">
            <div className="text-center space-y-2 max-w-2xl">
              <h2 className="text-3xl font-bold text-foreground">Property Risk Analysis</h2>
              <p className="text-muted-foreground">
                Enter a property address to receive comprehensive risk assessments for flood, wildfire, storm, and drought hazards.
              </p>
            </div>
            <AddressInput 
              onSubmit={handleAddressSubmit} 
              isLoading={isLoading}
              mapboxToken={mapboxToken}
              onTokenChange={handleTokenChange}
              showTokenInput={!import.meta.env.VITE_MAPBOX_API_KEY}
              resetKey={formResetKey}
            />
          </div>

          {/* Error Display */}
          {error && (
            <Alert variant="destructive" className="max-w-2xl mx-auto">
              <AlertCircle className="h-4 w-4" />
              <AlertDescription>{error}</AlertDescription>
            </Alert>
          )}

          {/* Results Section */}
          {report && (
            <div className="space-y-8 animate-in fade-in duration-500">
              {/* Location Info */}
              <Card className="max-w-2xl mx-auto">
                <CardHeader>
                  <CardTitle className="flex items-center gap-2">
                    <MapPin className="h-5 w-5 text-primary" />
                    Property Location
                  </CardTitle>
                </CardHeader>
                <CardContent className="space-y-2">
                  <p className="text-foreground font-medium">{report.location.address}</p>
                  <p className="text-sm text-muted-foreground">
                    Coordinates: {report.location.latitude >= 0 ? report.location.latitude.toFixed(4) + "°N" : Math.abs(report.location.latitude).toFixed(4) + "°S"}, {report.location.longitude >= 0 ? report.location.longitude.toFixed(4) + "°E" : Math.abs(report.location.longitude).toFixed(4) + "°W"}
                  </p>
                </CardContent>
              </Card>

              {/* Location Data (Earth Engine) */}
              {report.location_data && (
                <LocationDataCard locationData={report.location_data} />
              )}

              {/* Risk Scores Grid */}
              <div className="grid grid-cols-1 md:grid-cols-2 gap-6 max-w-5xl mx-auto">
                {report.risk_scores.map((risk) => (
                  <RiskScoreCard
                    key={risk.risk_type}
                    riskType={risk.risk_type}
                    score={risk.score}
                    explanation={risk.explanation}
                  />
                ))}
              </div>

              {/* Overall Summary */}
              <Card className="max-w-3xl mx-auto">
                <CardHeader>
                  <CardTitle className="flex items-center justify-between">
                    <span>Overall Assessment</span>
                    <DecisionBadge decision={report.automated_decision} />
                  </CardTitle>
                </CardHeader>
                <CardContent>
                  <p className="text-foreground leading-relaxed">{report.overall_summary}</p>
                </CardContent>
              </Card>
            </div>
          )}

          {/* Empty State */}
          {!report && !isLoading && !error && (
            <div className="text-center py-12 space-y-4 max-w-2xl mx-auto">
              <div className="flex justify-center">
                <Shield className="h-16 w-16 text-muted-foreground/50" />
              </div>
              <div className="space-y-2">
                <h3 className="text-xl font-semibold text-foreground">Ready to Assess Risk</h3>
                <p className="text-muted-foreground">
                  Enter a property address above to generate a comprehensive risk assessment report.
                </p>
              </div>
            </div>
          )}
        </div>
      </main>

      {/* Footer */}
      <footer className="border-t mt-16">
        <div className="container mx-auto px-4 py-6 text-center text-sm text-muted-foreground">
          <p>© 2025 AlphaEarth Insurance. Advanced risk assessment powered by AI.</p>
        </div>
      </footer>
    </div>
  );
};

export default Index;
