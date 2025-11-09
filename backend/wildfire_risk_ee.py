"""
Google Earth Engine-based wildfire risk calculation module.

This module uses Earth Engine datasets to calculate data-driven wildfire risk
scores based on satellite imagery, climate data, and historical fire records.
"""

import os
import logging
import traceback
from datetime import datetime, timedelta
from typing import Dict, Optional, Tuple

logger = logging.getLogger(__name__)

# Try to import Earth Engine, handle gracefully if not available
try:
    import ee
    EE_AVAILABLE = True
except ImportError:
    EE_AVAILABLE = False
    # Create a dummy class for type hints when ee is not available
    class ee:
        class Geometry:
            pass
    logger.warning("Earth Engine API not available. Install with: pip install earthengine-api")


def initialize_earth_engine() -> bool:
    """
    Initialize Earth Engine with authentication.
    Returns True if successful, False otherwise.
    """
    if not EE_AVAILABLE:
        return False
    
    try:
        # Check if already initialized
        if ee.data._initialized:
            logger.debug("Earth Engine already initialized")
            return True
        
        # Try to initialize with service account credentials if available
        credentials_path = os.getenv("EARTH_ENGINE_CREDENTIALS")
        if credentials_path and os.path.exists(credentials_path):
            logger.info(f"Initializing Earth Engine with service account: {credentials_path}")
            credentials = ee.ServiceAccountCredentials(None, credentials_path)
            ee.Initialize(credentials)
        else:
            # Try to initialize with default credentials (user auth)
            logger.info("Initializing Earth Engine with default credentials")
            ee.Initialize()
        
        logger.info("Earth Engine initialized successfully")
        return True
    except Exception as e:
        logger.error(f"Failed to initialize Earth Engine: {e}")
        logger.debug(traceback.format_exc())
        return False


def get_ndvi_data(point: ee.Geometry, buffer_km: float = 5.0) -> Optional[float]:
    """
    Extract NDVI (Normalized Difference Vegetation Index) data.
    Higher NDVI indicates more vegetation/fuel load.
    
    Args:
        point: Earth Engine Geometry point
        buffer_km: Buffer radius in kilometers
        
    Returns:
        Average NDVI value (0-1) or None if extraction fails
    """
    try:
        region = point.buffer(buffer_km * 1000)  # Convert km to meters
        
        # MODIS NDVI dataset (16-day composite)
        ndvi_collection = ee.ImageCollection('MODIS/006/MOD13Q1') \
            .filterDate(datetime.now() - timedelta(days=90), datetime.now()) \
            .select('NDVI') \
            .filterBounds(region)
        
        # Get the most recent image
        latest = ndvi_collection.sort('system:time_start', False).first()
        
        # Calculate mean NDVI in the region
        ndvi_value = latest.reduceRegion(
            reducer=ee.Reducer.mean(),
            geometry=region,
            scale=250,  # MODIS resolution
            maxPixels=1e9
        ).get('NDVI')
        
        # Convert to Python value (NDVI is scaled 0-10000, normalize to 0-1)
        ndvi = ndvi_value.getInfo() / 10000.0 if ndvi_value else None
        return ndvi
    except Exception as e:
        logger.warning(f"Failed to extract NDVI data: {e}")
        return None


def get_temperature_data(point: ee.Geometry, buffer_km: float = 5.0) -> Optional[Tuple[float, float]]:
    """
    Extract land surface temperature data and calculate anomaly.
    
    Args:
        point: Earth Engine Geometry point
        buffer_km: Buffer radius in kilometers
        
    Returns:
        Tuple of (current_temp, historical_avg_temp) in Celsius, or None
    """
    try:
        region = point.buffer(buffer_km * 1000)
        
        # MODIS Land Surface Temperature
        temp_collection = ee.ImageCollection('MODIS/006/MOD11A2') \
            .select('LST_Day_1km') \
            .filterBounds(region)
        
        # Current temperature (last 30 days)
        current = temp_collection.filterDate(
            datetime.now() - timedelta(days=30),
            datetime.now()
        ).mean()
        
        # Historical average (same period last year, 3-year average)
        historical_start = datetime.now() - timedelta(days=1095)  # 3 years ago
        historical_end = datetime.now() - timedelta(days=365)
        historical = temp_collection.filterDate(historical_start, historical_end).mean()
        
        # Extract values
        current_temp = current.reduceRegion(
            reducer=ee.Reducer.mean(),
            geometry=region,
            scale=1000,
            maxPixels=1e9
        ).get('LST_Day_1km')
        
        hist_temp = historical.reduceRegion(
            reducer=ee.Reducer.mean(),
            geometry=region,
            scale=1000,
            maxPixels=1e9
        ).get('LST_Day_1km')
        
        # MODIS LST is in Kelvin * 0.02, convert to Celsius
        current_c = (current_temp.getInfo() * 0.02 - 273.15) if current_temp else None
        hist_c = (hist_temp.getInfo() * 0.02 - 273.15) if hist_temp else None
        
        return (current_c, hist_c) if (current_c is not None and hist_c is not None) else None
    except Exception as e:
        logger.warning(f"Failed to extract temperature data: {e}")
        return None


def get_precipitation_data(point: ee.Geometry, buffer_km: float = 5.0) -> Optional[Tuple[float, float]]:
    """
    Extract precipitation data and calculate deficit.
    
    Args:
        point: Earth Engine Geometry point
        buffer_km: Buffer radius in kilometers
        
    Returns:
        Tuple of (current_precip, historical_avg_precip) in mm, or None
    """
    try:
        region = point.buffer(buffer_km * 1000)
        
        # CHIRPS Daily Precipitation
        precip_collection = ee.ImageCollection('UCSB-CHG/CHIRPS/DAILY') \
            .select('precipitation') \
            .filterBounds(region)
        
        # Current precipitation (last 90 days)
        current = precip_collection.filterDate(
            datetime.now() - timedelta(days=90),
            datetime.now()
        ).sum()
        
        # Historical average (same period, 5-year average)
        historical_start = datetime.now() - timedelta(days=1825)  # 5 years ago
        historical_end = datetime.now() - timedelta(days=365)
        historical = precip_collection.filterDate(
            historical_start,
            historical_end
        ).filter(
            ee.Filter.dayOfYear(
                (datetime.now() - timedelta(days=90)).timetuple().tm_yday,
                datetime.now().timetuple().tm_yday
            )
        ).mean().multiply(90)  # Average daily * 90 days
        
        # Extract values
        current_precip = current.reduceRegion(
            reducer=ee.Reducer.mean(),
            geometry=region,
            scale=5566,  # CHIRPS resolution
            maxPixels=1e9
        ).get('precipitation')
        
        hist_precip = historical.reduceRegion(
            reducer=ee.Reducer.mean(),
            geometry=region,
            scale=5566,
            maxPixels=1e9
        ).get('precipitation')
        
        current_mm = current_precip.getInfo() if current_precip else None
        hist_mm = hist_precip.getInfo() if hist_precip else None
        
        return (current_mm, hist_mm) if (current_mm is not None and hist_mm is not None) else None
    except Exception as e:
        logger.warning(f"Failed to extract precipitation data: {e}")
        return None


def get_historical_fire_data(point: ee.Geometry, buffer_km: float = 10.0) -> Optional[int]:
    """
    Count historical fires in the region.
    
    Args:
        point: Earth Engine Geometry point
        buffer_km: Buffer radius in kilometers (larger for fire history)
        
    Returns:
        Number of fires in the last 5 years, or None
    """
    try:
        region = point.buffer(buffer_km * 1000)
        
        # MODIS Burned Area dataset
        fire_collection = ee.ImageCollection('MODIS/006/MCD64A1') \
            .filterDate(datetime.now() - timedelta(days=1825), datetime.now()) \
            .select('BurnDate') \
            .filterBounds(region)
        
        # Count unique burn dates (each date represents a fire event)
        # Create a mask where BurnDate > 0 (burned area)
        burned_areas = fire_collection.map(lambda img: img.gt(0))
        
        # Sum all burned areas and count pixels
        total_burned = burned_areas.sum()
        
        # Count pixels with at least one fire
        fire_count = total_burned.reduceRegion(
            reducer=ee.Reducer.count(),
            geometry=region,
            scale=500,  # MODIS resolution
            maxPixels=1e9
        ).get('BurnDate')
        
        # Alternative: count distinct fire events by counting images with burned area
        # This is a simplified approach - count images with significant burned area
        fire_events = fire_collection.size().getInfo()
        
        return fire_events if fire_events else 0
    except Exception as e:
        logger.warning(f"Failed to extract historical fire data: {e}")
        return None


def get_elevation_data(point: ee.Geometry, buffer_km: float = 5.0) -> Optional[float]:
    """
    Extract elevation data.
    
    Args:
        point: Earth Engine Geometry point
        buffer_km: Buffer radius in kilometers
        
    Returns:
        Average elevation in meters, or None
    """
    try:
        region = point.buffer(buffer_km * 1000)
        
        # NASA NASADEM elevation dataset
        elevation = ee.Image('NASA/NASADEM_HGT/001').select('elevation')
        
        elev_value = elevation.reduceRegion(
            reducer=ee.Reducer.mean(),
            geometry=region,
            scale=30,  # 30m resolution
            maxPixels=1e9
        ).get('elevation')
        
        return elev_value.getInfo() if elev_value else None
    except Exception as e:
        logger.warning(f"Failed to extract elevation data: {e}")
        return None


def calculate_risk_score(
    ndvi: Optional[float],
    temp_data: Optional[Tuple[float, float]],
    precip_data: Optional[Tuple[float, float]],
    fire_count: Optional[int],
    elevation: Optional[float]
) -> Tuple[float, str]:
    """
    Calculate wildfire risk score (0-10) using weighted factors.
    
    Weights:
    - Historical fire frequency: 30%
    - Current vegetation/fuel load (NDVI): 25%
    - Temperature anomalies: 20%
    - Precipitation deficit: 15%
    - Elevation/terrain: 10%
    
    Args:
        ndvi: NDVI value (0-1)
        temp_data: Tuple of (current_temp, historical_avg_temp) in Celsius
        precip_data: Tuple of (current_precip, historical_avg_precip) in mm
        fire_count: Number of historical fires
        elevation: Elevation in meters
        
    Returns:
        Tuple of (risk_score 0-10, explanation string)
    """
    score_components = []
    explanations = []
    
    # 1. Historical fire frequency (30% weight)
    if fire_count is not None:
        # Normalize fire count to 0-10 scale
        # 0 fires = 0, 1-2 fires = 2-4, 3-5 fires = 5-7, 6+ fires = 8-10
        if fire_count == 0:
            fire_score = 0
            fire_expl = "No historical fires in the region"
        elif fire_count <= 2:
            fire_score = 2 + (fire_count - 1) * 2
            fire_expl = f"{fire_count} historical fire(s) detected"
        elif fire_count <= 5:
            fire_score = 5 + (fire_count - 3) * 1
            fire_expl = f"{fire_count} historical fires indicate moderate risk"
        else:
            fire_score = min(10, 8 + (fire_count - 6) * 0.5)
            fire_expl = f"{fire_count} historical fires indicate high risk"
        
        score_components.append(("fire_frequency", fire_score, 0.30))
        explanations.append(fire_expl)
    else:
        score_components.append(("fire_frequency", 5.0, 0.30))  # Default moderate
        explanations.append("Historical fire data unavailable")
    
    # 2. Vegetation/fuel load - NDVI (25% weight)
    if ndvi is not None:
        # Higher NDVI = more vegetation = more fuel = higher risk
        # NDVI 0-0.3 (sparse) = 0-3, 0.3-0.6 (moderate) = 3-7, 0.6+ (dense) = 7-10
        if ndvi < 0.3:
            veg_score = ndvi / 0.3 * 3
            veg_expl = "Low vegetation density"
        elif ndvi < 0.6:
            veg_score = 3 + ((ndvi - 0.3) / 0.3) * 4
            veg_expl = "Moderate vegetation density"
        else:
            veg_score = 7 + min(3, ((ndvi - 0.6) / 0.4) * 3)
            veg_expl = "High vegetation density (high fuel load)"
        
        score_components.append(("vegetation", veg_score, 0.25))
        explanations.append(veg_expl)
    else:
        score_components.append(("vegetation", 5.0, 0.25))
        explanations.append("Vegetation data unavailable")
    
    # 3. Temperature anomalies (20% weight)
    if temp_data:
        current_temp, hist_temp = temp_data
        temp_anomaly = current_temp - hist_temp
        
        # Positive anomaly = higher risk
        # -5°C or less = 0, 0°C = 5, +5°C or more = 10
        if temp_anomaly <= -5:
            temp_score = 0
            temp_expl = f"Temperature {temp_anomaly:.1f}°C below average"
        elif temp_anomaly <= 0:
            temp_score = 5 + (temp_anomaly / -5) * 5
            temp_expl = f"Temperature {temp_anomaly:.1f}°C below average"
        elif temp_anomaly <= 5:
            temp_score = 5 + (temp_anomaly / 5) * 5
            temp_expl = f"Temperature {temp_anomaly:.1f}°C above average"
        else:
            temp_score = 10
            temp_expl = f"Temperature {temp_anomaly:.1f}°C above average (high risk)"
        
        score_components.append(("temperature", temp_score, 0.20))
        explanations.append(temp_expl)
    else:
        score_components.append(("temperature", 5.0, 0.20))
        explanations.append("Temperature data unavailable")
    
    # 4. Precipitation deficit (15% weight)
    if precip_data:
        current_precip, hist_precip = precip_data
        precip_deficit = ((hist_precip - current_precip) / hist_precip * 100) if hist_precip > 0 else 0
        
        # Higher deficit = higher risk
        # 0% deficit = 0, 50% deficit = 7.5, 100%+ deficit = 10
        if precip_deficit <= 0:
            precip_score = 0
            precip_expl = "Precipitation at or above average"
        elif precip_deficit <= 50:
            precip_score = (precip_deficit / 50) * 7.5
            precip_expl = f"{precip_deficit:.0f}% precipitation deficit"
        else:
            precip_score = 7.5 + min(2.5, ((precip_deficit - 50) / 50) * 2.5)
            precip_expl = f"{precip_deficit:.0f}% precipitation deficit (severe drought)"
        
        score_components.append(("precipitation", precip_score, 0.15))
        explanations.append(precip_expl)
    else:
        score_components.append(("precipitation", 5.0, 0.15))
        explanations.append("Precipitation data unavailable")
    
    # 5. Elevation/terrain (10% weight)
    if elevation is not None:
        # Higher elevation can mean more complex terrain, but also cooler temps
        # Very low elevation (<100m) = 2, moderate (100-500m) = 5, high (>500m) = 8
        if elevation < 100:
            elev_score = 2
            elev_expl = "Low elevation"
        elif elevation < 500:
            elev_score = 2 + ((elevation - 100) / 400) * 6
            elev_expl = f"Moderate elevation ({elevation:.0f}m)"
        else:
            elev_score = 8 + min(2, ((elevation - 500) / 1000) * 2)
            elev_expl = f"High elevation ({elevation:.0f}m, complex terrain)"
        
        score_components.append(("elevation", elev_score, 0.10))
        explanations.append(elev_expl)
    else:
        score_components.append(("elevation", 5.0, 0.10))
        explanations.append("Elevation data unavailable")
    
    # Calculate weighted score
    total_score = sum(score * weight for _, score, weight in score_components)
    
    # Create explanation
    explanation = ". ".join(explanations[:3])  # Top 3 factors
    if len(explanations) > 3:
        explanation += "."
    
    return (round(total_score, 1), explanation)


def calculate_wildfire_risk_ee(lat: float, lon: float, timeout_seconds: int = 30) -> Optional[Dict]:
    """
    Calculate wildfire risk using Google Earth Engine data.
    
    Args:
        lat: Latitude
        lon: Longitude
        timeout_seconds: Maximum time to wait for Earth Engine operations
        
    Returns:
        Dictionary with 'score' (0-10), 'explanation', and 'data_sources' keys,
        or None if calculation fails
    """
    if not EE_AVAILABLE:
        logger.warning("Earth Engine API not available")
        return None
    
    # Initialize Earth Engine
    if not initialize_earth_engine():
        logger.warning("Failed to initialize Earth Engine")
        return None
    
    try:
        logger.info(f"Calculating wildfire risk for coordinates: ({lat}, {lon})")
        
        # Create point geometry
        point = ee.Geometry.Point([lon, lat])
        
        # Extract data from various sources
        logger.debug("Extracting NDVI data...")
        ndvi = get_ndvi_data(point)
        
        logger.debug("Extracting temperature data...")
        temp_data = get_temperature_data(point)
        
        logger.debug("Extracting precipitation data...")
        precip_data = get_precipitation_data(point)
        
        logger.debug("Extracting historical fire data...")
        fire_count = get_historical_fire_data(point)
        
        logger.debug("Extracting elevation data...")
        elevation = get_elevation_data(point)
        
        # Calculate risk score
        score, explanation = calculate_risk_score(
            ndvi, temp_data, precip_data, fire_count, elevation
        )
        
        # Track which data sources were successfully retrieved
        data_sources = {
            "ndvi": ndvi is not None,
            "temperature": temp_data is not None,
            "precipitation": precip_data is not None,
            "historical_fires": fire_count is not None,
            "elevation": elevation is not None
        }
        
        logger.info(f"Wildfire risk calculated: {score}/10")
        
        return {
            "score": score,
            "explanation": explanation,
            "data_sources": data_sources,
            "raw_data": {
                "ndvi": ndvi,
                "temperature": temp_data,
                "precipitation": precip_data,
                "fire_count": fire_count,
                "elevation": elevation
            }
        }
        
    except Exception as e:
        logger.error(f"Error calculating wildfire risk with Earth Engine: {e}")
        logger.debug(traceback.format_exc())
        return None

