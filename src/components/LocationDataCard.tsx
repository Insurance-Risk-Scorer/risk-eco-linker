import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Separator } from "@/components/ui/separator";
import {
  TreePine,
  Flame,
  Leaf,
  Waves,
  AlertCircle,
} from "lucide-react";
import {
  getLandcoverName,
  formatDate,
  formatPercentage,
  getPrimaryLandcover,
  getLandcoverPercentages,
} from "@/lib/locationDataUtils";

interface LocationDataCardProps {
  locationData: any;
}

export const LocationDataCard = ({ locationData }: LocationDataCardProps) => {
  if (!locationData) {
    return null;
  }

  // Debug: Log to console
  console.log("LocationDataCard received data:", locationData);

  const worldcover = locationData.worldcover || {};
  const fireHistory = locationData.fire_history || {};
  const currentConditions = locationData.current_conditions || {};

  // Get primary landcover
  const primaryLandcover = getPrimaryLandcover(worldcover);
  
  // Get all landcover percentages
  const landcoverPercentages = getLandcoverPercentages(worldcover);

  // Fire history data
  const hasFire = fireHistory.has_fire || false;
  const lastFireDate = fireHistory.last_fire_date;
  const totalFires = fireHistory.total_fires_in_period || 0;
  const firesPerYear = fireHistory.fires_per_year || 0;

  // Vegetation and water data (from current conditions)
  const vegetation = currentConditions.vegetation || {};
  const waterCoverage = currentConditions.water_coverage;
  const nearbyWaterCoverage = currentConditions.nearby_water_coverage;
  const nearbyWaterDistance = currentConditions.nearby_water_distance_meters || 1000;

  // NDVI and EVI
  const ndvi = vegetation.NDVI?.NDVI_mean;
  const evi = vegetation.EVI?.EVI_mean;

  return (
    <Card className="max-w-3xl mx-auto">
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          <TreePine className="h-5 w-5 text-primary" />
          Location Data (Earth Engine)
        </CardTitle>
        <CardDescription>
          Detailed environmental data from satellite imagery and Earth observation datasets
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-6">
        {/* Landcover */}
        <div className="space-y-2">
          <div className="flex items-center gap-2">
            <TreePine className="h-4 w-4 text-muted-foreground" />
            <h4 className="font-semibold">Landcover (1km radius)</h4>
          </div>
          <div className="pl-6 space-y-2">
            {worldcover.error ? (
              <p className="text-sm text-muted-foreground">Error: {worldcover.error}</p>
            ) : landcoverPercentages.length > 0 ? (
              <div className="space-y-1.5">
                {landcoverPercentages.map((item) => (
                  <div
                    key={item.code}
                    className="flex items-center justify-between text-sm"
                  >
                    <span className="text-muted-foreground">{item.name}:</span>
                    <span className="font-medium">{formatPercentage(item.percentage)}</span>
                  </div>
                ))}
              </div>
            ) : (
              <Badge variant="outline" className="text-sm">
                {primaryLandcover.name}
              </Badge>
            )}
          </div>
        </div>

        <Separator />

        {/* Fire History */}
        <div className="space-y-2">
          <div className="flex items-center gap-2">
            <Flame className="h-4 w-4 text-muted-foreground" />
            <h4 className="font-semibold">Fire History</h4>
          </div>
          <div className="pl-6 space-y-2">
            {fireHistory.error ? (
              <p className="text-sm text-muted-foreground">Error: {fireHistory.error}</p>
            ) : (
              <>
                <div className="flex items-center gap-2">
                  <span className="text-sm text-muted-foreground">Historical fires:</span>
                  <Badge variant={hasFire ? "destructive" : "secondary"}>
                    {hasFire ? "Yes" : "No"}
                  </Badge>
                </div>
                {hasFire && lastFireDate && (
                  <div className="text-sm">
                    <span className="text-muted-foreground">Last fire: </span>
                    <span className="font-medium">{formatDate(lastFireDate)}</span>
                  </div>
                )}
                <div className="text-sm">
                  <span className="text-muted-foreground">Total fires in period: </span>
                  <span className="font-medium">{totalFires}</span>
                </div>
                <div className="text-sm">
                  <span className="text-muted-foreground">Fires per year: </span>
                  <span className="font-medium">{firesPerYear.toFixed(2)}</span>
                </div>
              </>
            )}
          </div>
        </div>

        <Separator />

        {/* Vegetation Indices */}
        {(ndvi !== null && ndvi !== undefined) || (evi !== null && evi !== undefined) ? (
          <>
            <div className="space-y-2">
              <div className="flex items-center gap-2">
                <Leaf className="h-4 w-4 text-muted-foreground" />
                <h4 className="font-semibold">Vegetation Indices</h4>
              </div>
              <div className="pl-6 space-y-2">
                {ndvi !== null && ndvi !== undefined && (
                  <div className="flex items-center justify-between">
                    <span className="text-sm text-muted-foreground">NDVI:</span>
                    <span className="text-sm font-medium">{ndvi.toFixed(4)}</span>
                  </div>
                )}
                {evi !== null && evi !== undefined && (
                  <div className="flex items-center justify-between">
                    <span className="text-sm text-muted-foreground">EVI:</span>
                    <span className="text-sm font-medium">{evi.toFixed(4)}</span>
                  </div>
                )}
              </div>
            </div>
            <Separator />
          </>
        ) : null}

        {/* Water Coverage */}
        {(waterCoverage !== null && waterCoverage !== undefined) ||
        (nearbyWaterCoverage !== null && nearbyWaterCoverage !== undefined) ? (
          <div className="space-y-2">
            <div className="flex items-center gap-2">
              <Waves className="h-4 w-4 text-muted-foreground" />
              <h4 className="font-semibold">Water Coverage</h4>
            </div>
            <div className="pl-6 space-y-2">
              {waterCoverage !== null && waterCoverage !== undefined && (
                <div className="flex items-center justify-between">
                  <span className="text-sm text-muted-foreground">In area:</span>
                  <span className="text-sm font-medium">{formatPercentage(waterCoverage)}</span>
                </div>
              )}
              {nearbyWaterCoverage !== null && nearbyWaterCoverage !== undefined && (
                <div className="flex items-center justify-between">
                  <span className="text-sm text-muted-foreground">
                    Nearby ({nearbyWaterDistance}m radius):
                  </span>
                  <span className="text-sm font-medium">
                    {formatPercentage(nearbyWaterCoverage)}
                  </span>
                </div>
              )}
            </div>
          </div>
        ) : null}

        {/* Error message if all data failed */}
        {worldcover.error && fireHistory.error && (
          <div className="flex items-center gap-2 text-sm text-destructive">
            <AlertCircle className="h-4 w-4" />
            <span>Unable to load location data. Please try again later.</span>
          </div>
        )}
      </CardContent>
    </Card>
  );
};

