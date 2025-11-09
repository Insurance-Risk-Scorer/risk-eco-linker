import { useState, useEffect, useRef } from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { MapPin, Loader2, Key } from "lucide-react";
import { Card } from "@/components/ui/card";

interface AddressInputProps {
  onSubmit: (address: string, coordinates: { lat: number; lng: number }) => void;
  isLoading: boolean;
  mapboxToken: string;
  onTokenChange: (token: string) => void;
  showTokenInput?: boolean;
}

interface MapboxFeature {
  id: string;
  place_name: string;
  center: [number, number];
}

export const AddressInput = ({ onSubmit, isLoading, mapboxToken, onTokenChange, showTokenInput = true }: AddressInputProps) => {
  const [address, setAddress] = useState("");
  const [suggestions, setSuggestions] = useState<MapboxFeature[]>([]);
  const [showSuggestions, setShowSuggestions] = useState(false);
  const [selectedCoordinates, setSelectedCoordinates] = useState<{ lat: number; lng: number } | null>(null);
  const wrapperRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const handleClickOutside = (event: MouseEvent) => {
      if (wrapperRef.current && !wrapperRef.current.contains(event.target as Node)) {
        setShowSuggestions(false);
      }
    };
    document.addEventListener("mousedown", handleClickOutside);
    return () => document.removeEventListener("mousedown", handleClickOutside);
  }, []);

  useEffect(() => {
    const fetchSuggestions = async () => {
      if (!address.trim() || !mapboxToken || address.length < 3) {
        setSuggestions([]);
        return;
      }

      try {
        const response = await fetch(
          `https://api.mapbox.com/geocoding/v5/mapbox.places/${encodeURIComponent(address)}.json?access_token=${mapboxToken}&autocomplete=true&limit=5`
        );
        
        if (response.ok) {
          const data = await response.json();
          setSuggestions(data.features || []);
          setShowSuggestions(true);
        }
      } catch (error) {
        console.error("Error fetching suggestions:", error);
      }
    };

    const debounce = setTimeout(fetchSuggestions, 300);
    return () => clearTimeout(debounce);
  }, [address, mapboxToken]);

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (address.trim() && selectedCoordinates) {
      onSubmit(address.trim(), selectedCoordinates);
      setShowSuggestions(false);
    }
  };

  const handleSelectSuggestion = (feature: MapboxFeature) => {
    setAddress(feature.place_name);
    setSelectedCoordinates({ lat: feature.center[1], lng: feature.center[0] });
    setShowSuggestions(false);
    setSuggestions([]);
  };

  return (
    <form onSubmit={handleSubmit} className="w-full max-w-2xl space-y-4">
      {showTokenInput && !mapboxToken && (
        <Card className="p-4 bg-muted/50">
          <div className="flex items-start gap-3">
            <Key className="h-5 w-5 text-primary mt-0.5" />
            <div className="flex-1 space-y-2">
              <p className="text-sm text-muted-foreground">
                Enter your Mapbox public token to enable address autocomplete. Get it from{" "}
                <a 
                  href="https://account.mapbox.com/access-tokens/" 
                  target="_blank" 
                  rel="noopener noreferrer"
                  className="text-primary hover:underline"
                >
                  Mapbox Dashboard
                </a>
              </p>
              <Input
                type="text"
                placeholder="pk.eyJ1..."
                value={mapboxToken}
                onChange={(e) => onTokenChange(e.target.value)}
                className="h-10"
              />
            </div>
          </div>
        </Card>
      )}
      
      <div className="relative" ref={wrapperRef}>
        <MapPin className="absolute left-3 top-1/2 -translate-y-1/2 h-5 w-5 text-muted-foreground z-10" />
        <Input
          type="text"
          placeholder="Enter property address (e.g., 123 Main St, San Francisco, CA)"
          value={address}
          onChange={(e) => {
            setAddress(e.target.value);
            setSelectedCoordinates(null);
          }}
          disabled={isLoading}
          className="pl-11 h-14 text-lg"
        />
        
        {showSuggestions && suggestions.length > 0 && (
          <Card className="absolute z-50 w-full mt-1 max-h-80 overflow-auto">
            <div className="py-2">
              {suggestions.map((feature) => (
                <button
                  key={feature.id}
                  type="button"
                  onClick={() => handleSelectSuggestion(feature)}
                  className="w-full px-4 py-3 text-left hover:bg-muted transition-colors flex items-start gap-3"
                >
                  <MapPin className="h-4 w-4 text-muted-foreground mt-1 flex-shrink-0" />
                  <span className="text-sm text-foreground">{feature.place_name}</span>
                </button>
              ))}
            </div>
          </Card>
        )}
      </div>
      
      <Button
        type="submit"
        disabled={!address.trim() || !selectedCoordinates || isLoading}
        className="w-full h-12 text-base"
        size="lg"
      >
        {isLoading ? (
          <>
            <Loader2 className="mr-2 h-5 w-5 animate-spin" />
            Analyzing Risk...
          </>
        ) : (
          "Get Risk Assessment"
        )}
      </Button>
    </form>
  );
};

