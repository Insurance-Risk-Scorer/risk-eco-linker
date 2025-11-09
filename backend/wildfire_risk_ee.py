"""
Google Earth Engine-based wildfire risk calculation module.

This module uses Earth Engine datasets to calculate data-driven wildfire risk
scores based on satellite imagery, climate data, and historical fire records.
Adapted from get_worldcover_data.py with working implementations.
"""

import os
import logging
import traceback
import pathlib
import time
import math
from datetime import datetime, timedelta
from typing import Dict, Optional, Tuple

logger = logging.getLogger(__name__)

# Try to import Earth Engine, handle gracefully if not available
try:
    import ee
    EE_AVAILABLE = True
except ImportError:
    EE_AVAILABLE = False
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
        if credentials_path:
            # Resolve path relative to root directory if not absolute
            if not os.path.isabs(credentials_path):
                root_dir = pathlib.Path(__file__).parent.parent
                credentials_path = str(root_dir / credentials_path)
            
            if os.path.exists(credentials_path):
                logger.info(f"Initializing Earth Engine with service account: {credentials_path}")
                credentials = ee.ServiceAccountCredentials(None, credentials_path)
                ee.Initialize(credentials)
            else:
                logger.warning(f"Earth Engine credentials file not found: {credentials_path}, falling back to default auth")
                ee.Initialize()
        else:
            # Try to initialize with default credentials (user auth)
            # Also check for credentials.json in root directory
            root_dir = pathlib.Path(__file__).parent.parent
            credentials_path = root_dir / "credentials.json"
            if credentials_path.exists():
                try:
                    import json
                    with open(credentials_path, 'r') as f:
                        creds = json.load(f)
                        project_id = creds.get('project_id')
                    
                    credentials = ee.ServiceAccountCredentials(None, str(credentials_path))
                    if project_id:
                        ee.Initialize(credentials, project=project_id)
                    else:
                        ee.Initialize(credentials)
                    logger.info("Earth Engine initialized with credentials.json")
                except Exception as e:
                    logger.warning(f"Failed to initialize with credentials.json: {e}, trying default auth")
                    ee.Initialize()
            else:
                logger.info("Initializing Earth Engine with default credentials")
                ee.Initialize()
        
        logger.info("Earth Engine initialized successfully")
        return True
    except Exception as e:
        logger.error(f"Failed to initialize Earth Engine: {e}")
        logger.debug(traceback.format_exc())
        return False


def get_square_from_coordinates(lat: float, lon: float, size_meters: int = 10) -> ee.Geometry:
    """
    Creates a square geometry around given coordinates.
    
    Args:
        lat: Latitude
        lon: Longitude
        size_meters: Size of the square in meters (default: 10m)
    
    Returns:
        ee.Geometry.Rectangle: A square as Rectangle
    """
    center = ee.Geometry.Point([lon, lat])
    
    # Convert meters to degrees (approximately)
    # 1 degree ≈ 111,320 meters (at equator)
    # At latitude lat: 1 degree longitude ≈ 111,320 * cos(lat) meters
    meters_per_degree_lat = 111320  # Latitude is constant
    lat_rad = math.radians(lat)
    meters_per_degree_lon = 111320 * math.cos(lat_rad)
    
    # Half size in degrees
    half_size_lat = (size_meters / 2) / meters_per_degree_lat
    half_size_lon = (size_meters / 2) / meters_per_degree_lon
    
    # Create Rectangle around the center point
    square = ee.Geometry.Rectangle([
        lon - half_size_lon,  # West
        lat - half_size_lat,  # South
        lon + half_size_lon,  # East
        lat + half_size_lat   # North
    ])
    
    return square


def get_landcover_classes() -> Dict[int, str]:
    """
    Returns a dictionary with landcover classes.
    
    Returns:
        dict: Mapping from class value to description
    """
    return {
        10: "Baumbestand",
        20: "Shrubland",
        30: "Wiese",
        40: "Ackerland",
        50: "Aufgebaut",
        60: "Karge / spärliche Vegetation",
        70: "Schnee und Eis",
        80: "Dauerhafte Gewässer",
        90: "Krautiges Feuchtgebiet",
        95: "Mangroven",
        100: "Moos und Flechten"
    }


def load_worldcover() -> ee.Image:
    """
    Loads the ESA WorldCover dataset.
    
    Returns:
        ee.Image: The first image from the WorldCover ImageCollection
    """
    dataset = ee.ImageCollection("ESA/WorldCover/v100").first()
    return dataset


def extract_square_data(image: ee.Image, square: ee.Geometry) -> dict:
    """
    Extracts all pixel data for the square.
    
    Args:
        image: ee.Image - The WorldCover image
        square: ee.Geometry - The square geometry
    
    Returns:
        dict: Dictionary with extracted data
    """
    samples = image.sample(
        region=square,
        scale=10,  # 10m resolution
        numPixels=100,
        geometries=True
    )
    
    features = samples.getInfo()
    return features


def get_square_statistics(image: ee.Image, square: ee.Geometry) -> dict:
    """
    Calculates statistics for the square.
    
    Args:
        image: ee.Image - The WorldCover image
        square: ee.Geometry - The square geometry
    
    Returns:
        dict: Dictionary with statistics
    """
    histogram = image.select('Map').reduceRegion(
        reducer=ee.Reducer.frequencyHistogram(),
        geometry=square,
        scale=10,
        maxPixels=1e9
    )
    
    stats = histogram.getInfo()
    return stats


def extract_multiple_statistics(image: ee.Image, square: ee.Geometry, band_names: list, scale: float = 1000, debug: bool = False) -> dict:
    """
    Extracts statistics for multiple bands simultaneously (faster).
    
    Args:
        image: ee.Image - The image
        square: ee.Geometry - The square geometry
        band_names: list - List of band names
        scale: float - Resolution in meters
        debug: bool - If True, debug info is printed
    
    Returns:
        dict: Dictionary with statistics for all bands
    """
    available_bands = image.bandNames().getInfo()
    if debug:
        logger.debug(f"Available bands: {available_bands}")
        missing_bands = [b for b in band_names if b not in available_bands]
        if missing_bands:
            logger.warning(f"Missing bands: {missing_bands}")
    
    valid_bands = [b for b in band_names if b in available_bands]
    if not valid_bands:
        if debug:
            logger.warning("None of the requested bands are available!")
        return {}
    
    # For very small geometries (like 10x10m square): Use sample() at center point
    center = square.centroid()
    
    sample = image.select(valid_bands).sample(
        region=center,
        scale=scale,
        numPixels=1
    )
    
    sample_info = sample.getInfo()
    
    result = {}
    if sample_info and 'features' in sample_info and len(sample_info['features']) > 0:
        props = sample_info['features'][0].get('properties', {})
        for band in valid_bands:
            value = props.get(band)
            if value is not None:
                result[f'{band}_mean'] = value
                result[f'{band}_min'] = value
                result[f'{band}_max'] = value
    
    if debug:
        logger.debug(f"Extracted stats: {result}")
    
    return result


def get_latest_image(collection: ee.ImageCollection, date: str, debug: bool = False) -> ee.Image:
    """
    Gets the latest available image before/after a date.
    
    Args:
        collection: ee.ImageCollection - The ImageCollection
        date: str - Date in format "YYYY-MM-DD"
        debug: bool - If True, debug info is printed
    
    Returns:
        ee.Image: The latest image
    """
    date_obj = datetime.strptime(date, "%Y-%m-%d")
    end_date = (date_obj + timedelta(days=1)).strftime("%Y-%m-%d")
    
    filtered = collection.filterDate('2000-01-01', end_date).sort('system:time_start', False)
    
    if debug:
        count = filtered.size().getInfo()
        logger.debug(f"{count} images found for date <= {date}")
    
    return filtered.first()


def load_gldas_data(date: str = None, debug: bool = False) -> ee.Image:
    """
    Loads GLDAS-2.0 data for a specific date.
    GLDAS V20 only goes until 2014, so we use the latest available image.
    
    Args:
        date: str - Date in format "YYYY-MM-DD" (default: current date or latest available)
        debug: bool - If True, debug info is printed
    
    Returns:
        ee.Image: The latest available GLDAS image
    """
    if date is None:
        date = datetime.now().strftime("%Y-%m-%d")
    
    collection = ee.ImageCollection("NASA/GLDAS/V20/NOAH/G025/T3H")
    
    date_obj = datetime.strptime(date, "%Y-%m-%d")
    start_date = date_obj.strftime("%Y-%m-%d")
    end_date = (date_obj + timedelta(days=1)).strftime("%Y-%m-%d")
    
    filtered = collection.filterDate(start_date, end_date)
    image = filtered.first()
    
    if debug:
        count = filtered.size().getInfo()
        logger.debug(f"{count} images found for {start_date}")
    
    return image


def get_all_gldas_data(square: ee.Geometry, date: str = None, debug: bool = False) -> dict:
    """
    Extracts all GLDAS data in a single query (faster).
    
    Args:
        square: ee.Geometry - The square geometry
        date: str - Date in format "YYYY-MM-DD" (default: current date)
        debug: bool - If True, debug info is printed
    
    Returns:
        dict: Dictionary with all GLDAS statistics
    """
    if date is None:
        date = datetime.now().strftime("%Y-%m-%d")
    
    try:
        image = load_gldas_data(date, debug=debug)
        
        # Check if image is valid
        try:
            image_info = image.getInfo()
            if not image_info or 'bands' not in image_info:
                raise Exception("Image is empty or invalid")
        except Exception as e:
            if debug:
                logger.warning(f"Error checking image: {e}")
            return {
                'surface_temperature': {'error': str(e)},
                'soil_moisture': {'error': str(e)},
                'soil_temperature': {'error': str(e)},
                'wind_speed': {'error': str(e)}
            }
        
        band_names = ['AvgSurfT_inst', 'SoilMoi0_10cm_inst', 'SoilTMP0_10cm_inst', 'Wind_f_inst']
        all_stats = extract_multiple_statistics(image, square, band_names, scale=25000, debug=debug)
        
        result = {
            'surface_temperature': {
                'AvgSurfT_inst_mean': all_stats.get('AvgSurfT_inst_mean'),
                'AvgSurfT_inst_min': all_stats.get('AvgSurfT_inst_min'),
                'AvgSurfT_inst_max': all_stats.get('AvgSurfT_inst_max')
            },
            'soil_moisture': {
                'SoilMoi0_10cm_inst_mean': all_stats.get('SoilMoi0_10cm_inst_mean'),
                'SoilMoi0_10cm_inst_min': all_stats.get('SoilMoi0_10cm_inst_min'),
                'SoilMoi0_10cm_inst_max': all_stats.get('SoilMoi0_10cm_inst_max')
            },
            'soil_temperature': {
                'SoilTMP0_10cm_inst_mean': all_stats.get('SoilTMP0_10cm_inst_mean'),
                'SoilTMP0_10cm_inst_min': all_stats.get('SoilTMP0_10cm_inst_min'),
                'SoilTMP0_10cm_inst_max': all_stats.get('SoilTMP0_10cm_inst_max')
            },
            'wind_speed': {
                'Wind_f_inst_mean': all_stats.get('Wind_f_inst_mean'),
                'Wind_f_inst_min': all_stats.get('Wind_f_inst_min'),
                'Wind_f_inst_max': all_stats.get('Wind_f_inst_max')
            }
        }
        
        return result
    except Exception as e:
        logger.warning(f"Error extracting GLDAS data: {e}")
        return {
            'surface_temperature': {'error': str(e)},
            'soil_moisture': {'error': str(e)},
            'soil_temperature': {'error': str(e)},
            'wind_speed': {'error': str(e)}
        }


def load_modis_ndvi(date: str = None) -> ee.Image:
    """
    Loads MODIS vegetation indices for a specific date.
    
    Args:
        date: str - Date in format "YYYY-MM-DD" (default: current date)
    
    Returns:
        ee.Image: The latest available MODIS NDVI image
    """
    if date is None:
        date = datetime.now().strftime("%Y-%m-%d")
    
    collection = ee.ImageCollection("MODIS/061/MOD13A1")
    return get_latest_image(collection, date)


def get_vegetation_indices(square: ee.Geometry, date: str = None, debug: bool = False) -> dict:
    """
    Extracts vegetation indices (NDVI, EVI) for the square.
    
    Args:
        square: ee.Geometry - The square geometry
        date: str - Date in format "YYYY-MM-DD" (default: current date)
        debug: bool - If True, debug info is printed
    
    Returns:
        dict: Dictionary with NDVI and EVI statistics
    """
    if date is None:
        date = datetime.now().strftime("%Y-%m-%d")
    
    try:
        image = load_modis_ndvi(date)
        center = square.centroid()
        sample = image.select(['NDVI', 'EVI']).sample(
            region=center,
            scale=500,
            numPixels=1
        )
        sample_info = sample.getInfo()
        
        all_stats = {}
        if sample_info and 'features' in sample_info and len(sample_info['features']) > 0:
            props = sample_info['features'][0].get('properties', {})
            for band in ['NDVI', 'EVI']:
                value = props.get(band)
                if value is not None:
                    # MODIS NDVI/EVI are scaled (0-10000), divide by 10000
                    scaled_value = value / 10000.0 if value > 1 else value
                    all_stats[f'{band}_mean'] = scaled_value
                    all_stats[f'{band}_min'] = scaled_value
                    all_stats[f'{band}_max'] = scaled_value
        
        result = {
            'NDVI': {
                'NDVI_mean': all_stats.get('NDVI_mean'),
                'NDVI_min': all_stats.get('NDVI_min'),
                'NDVI_max': all_stats.get('NDVI_max')
            },
            'EVI': {
                'EVI_mean': all_stats.get('EVI_mean'),
                'EVI_min': all_stats.get('EVI_min'),
                'EVI_max': all_stats.get('EVI_max')
            }
        }
        
        return result
    except Exception as e:
        if debug:
            logger.warning(f"Error extracting vegetation indices: {e}")
        return {'NDVI': {'error': str(e)}, 'EVI': {'error': str(e)}}


def get_historical_fires(square: ee.Geometry, start_date: str = None, end_date: str = None, debug: bool = False) -> dict:
    """
    Checks if there was ever a wildfire in the past in this pixel.
    FIRMS is an ImageCollection, not FeatureCollection!
    
    Args:
        square: ee.Geometry - The square geometry
        start_date: str - Start date in format "YYYY-MM-DD" (default: 10 years ago)
        end_date: str - End date in format "YYYY-MM-DD" (default: current date)
        debug: bool - If True, debug info is printed
    
    Returns:
        dict: Dictionary with fire statistics
    """
    if end_date is None:
        end_date = datetime.now().strftime("%Y-%m-%d")
    if start_date is None:
        start_date = (datetime.now() - timedelta(days=3650)).strftime("%Y-%m-%d")
    
    try:
        firms = ee.ImageCollection('FIRMS')
        filtered = firms.filterDate(start_date, end_date)
        
        center = square.centroid()
        fires_mosaic = filtered.select('T21').mosaic()
        
        fire_sample = fires_mosaic.sample(
            region=center,
            scale=1000,
            numPixels=1
        )
        
        fire_sample_info = fire_sample.getInfo()
        has_fire = False
        fire_value = None
        
        if fire_sample_info and 'features' in fire_sample_info and len(fire_sample_info['features']) > 0:
            props = fire_sample_info['features'][0].get('properties', {})
            fire_value = props.get('T21')
            has_fire = fire_value is not None and fire_value > 0
        
        fire_mask = fires_mosaic.gt(0)
        fire_count = fire_mask.reduceRegion(
            reducer=ee.Reducer.sum(),
            geometry=center.buffer(500),
            scale=1000,
            maxPixels=1e9,
            bestEffort=True
        )
        
        count_value = fire_count.getInfo().get('T21', 0)
        
        start = datetime.strptime(start_date, "%Y-%m-%d")
        end = datetime.strptime(end_date, "%Y-%m-%d")
        years = (end - start).days / 365.25
        
        fires_per_year = count_value / years if years > 0 else 0.0
        
        last_fire_date = None
        if has_fire:
            try:
                sorted_collection = filtered.sort('system:time_start', False)
                collection_size = filtered.size().getInfo()
                for i in range(min(20, collection_size)):
                    image = ee.Image(sorted_collection.toList(1, i).get(0))
                    fire_sample_img = image.select('T21').sample(
                        region=center,
                        scale=1000,
                        numPixels=1
                    )
                    fire_sample_img_info = fire_sample_img.getInfo()
                    if fire_sample_img_info and 'features' in fire_sample_img_info:
                        props = fire_sample_img_info['features'][0].get('properties', {})
                        t21_value = props.get('T21')
                        if t21_value and t21_value > 0:
                            date_prop = image.get('system:time_start').getInfo()
                            if date_prop:
                                last_fire_date = datetime.fromtimestamp(date_prop / 1000).strftime("%Y-%m-%d")
                                break
            except Exception as e:
                if debug:
                    logger.warning(f"Could not retrieve last fire date: {e}")
        
        result = {
            'has_fire': has_fire,
            'last_fire_date': last_fire_date,
            'total_fires_in_period': int(count_value),
            'fires_per_year': round(fires_per_year, 2)
        }
        
        return result
    except Exception as e:
        if debug:
            logger.warning(f"Error extracting fire history: {e}")
        return {'error': str(e)}


def load_water_mask() -> ee.Image:
    """
    Loads GLCF water mask.
    
    Returns:
        ee.Image: The water mask image
    """
    collection = ee.ImageCollection("GLCF/GLS_WATER")
    return collection.first()


def get_water_bodies(square: ee.Geometry, debug: bool = False) -> dict:
    """
    Extracts water body information for the square.
    
    Args:
        square: ee.Geometry - The square geometry
        debug: bool - If True, debug info is printed
    
    Returns:
        dict: Dictionary with water coverage statistics
    """
    try:
        image = load_water_mask()
        
        water_stats = image.select('water').reduceRegion(
            reducer=ee.Reducer.frequencyHistogram(),
            geometry=square,
            scale=30,
            maxPixels=1e9,
            bestEffort=True
        )
        
        stats = water_stats.getInfo()
        
        water_coverage = 0.0
        if 'water' in stats and stats['water']:
            histogram = stats['water']
            total_pixels = sum(float(v) for v in histogram.values())
            water_pixels = histogram.get('1', 0)
            if total_pixels > 0:
                water_coverage = (float(water_pixels) / total_pixels) * 100.0
        
        center = square.centroid()
        buffer = center.buffer(100)
        
        nearby_water_stats = image.select('water').reduceRegion(
            reducer=ee.Reducer.frequencyHistogram(),
            geometry=buffer,
            scale=30,
            maxPixels=1e9,
            bestEffort=True
        )
        
        nearby_stats = nearby_water_stats.getInfo()
        nearby_water_coverage = 0.0
        if 'water' in nearby_stats and nearby_stats['water']:
            histogram = nearby_stats['water']
            total_pixels = sum(float(v) for v in histogram.values())
            water_pixels = histogram.get('1', 0)
            if total_pixels > 0:
                nearby_water_coverage = (float(water_pixels) / total_pixels) * 100.0
        
        result = {
            'water_coverage_percent': water_coverage,
            'nearby_water_coverage_percent': nearby_water_coverage
        }
        
        return result
    except Exception as e:
        if debug:
            logger.warning(f"Error extracting water data: {e}")
        return {'error': str(e)}


def extract_all_risk_data(lat: float, lon: float, date: str = None, fire_history_start: str = None, debug: bool = False) -> dict:
    """
    Collects all wildfire risk data for the location.
    
    Args:
        lat: Latitude
        lon: Longitude
        date: str - Date in format "YYYY-MM-DD" (default: current date)
        fire_history_start: str - Start date for historical fires (default: 10 years ago)
        debug: bool - If True, debug info is printed
    
    Returns:
        dict: Dictionary with all extracted data
    """
    if date is None:
        date = datetime.now().strftime("%Y-%m-%d")
    if fire_history_start is None:
        fire_history_start = (datetime.now() - timedelta(days=3650)).strftime("%Y-%m-%d")
    
    square = get_square_from_coordinates(lat, lon, size_meters=10)
    
    all_data = {
        "square_info": {
            "center_lon": lon,
            "center_lat": lat,
            "size_meters": 10,
            "date": date
        },
        "worldcover": {},
        "fire_history": {},
        "current_conditions": {}
    }
    
    # WorldCover data
    try:
        worldcover = load_worldcover()
        features = extract_square_data(worldcover, square)
        stats = get_square_statistics(worldcover, square)
        all_data["worldcover"] = {
            "features": features,
            "statistics": stats
        }
    except Exception as e:
        logger.warning(f"Error extracting WorldCover data: {e}")
        all_data["worldcover"] = {"error": str(e)}
    
    # Historical fires
    try:
        fire_data = get_historical_fires(square, fire_history_start, date, debug=debug)
        all_data["fire_history"] = fire_data
    except Exception as e:
        logger.warning(f"Error extracting fire history: {e}")
        all_data["fire_history"] = {"error": str(e)}
    
    # Current conditions
    current_conditions = {}
    
    # GLDAS data
    try:
        gldas_data = get_all_gldas_data(square, date, debug=debug)
        current_conditions["surface_temperature"] = gldas_data["surface_temperature"]
        current_conditions["soil_moisture"] = gldas_data["soil_moisture"]
        current_conditions["soil_temperature"] = gldas_data["soil_temperature"]
        current_conditions["wind_speed"] = gldas_data["wind_speed"]
    except Exception as e:
        logger.warning(f"Error extracting GLDAS data: {e}")
        current_conditions["surface_temperature"] = {"error": str(e)}
        current_conditions["soil_moisture"] = {"error": str(e)}
        current_conditions["soil_temperature"] = {"error": str(e)}
        current_conditions["wind_speed"] = {"error": str(e)}
    
    # Vegetation indices
    try:
        vegetation = get_vegetation_indices(square, date, debug=debug)
        current_conditions["vegetation"] = vegetation
    except Exception as e:
        logger.warning(f"Error extracting vegetation indices: {e}")
        current_conditions["vegetation"] = {"error": str(e)}
    
    # Water bodies
    try:
        water = get_water_bodies(square, debug=debug)
        current_conditions["water_coverage"] = water.get("water_coverage_percent")
        current_conditions["nearby_water_coverage"] = water.get("nearby_water_coverage_percent")
    except Exception as e:
        logger.warning(f"Error extracting water data: {e}")
        current_conditions["water_coverage"] = None
        current_conditions["nearby_water_coverage"] = None
    
    all_data["current_conditions"] = current_conditions
    
    return all_data


def calculate_wildfire_risk_ee(lat: float, lon: float, timeout_seconds: int = 30) -> Optional[Dict]:
    """
    Calculate wildfire risk using Google Earth Engine data.
    Maintains backward compatibility with existing code.
    
    Args:
        lat: Latitude
        lon: Longitude
        timeout_seconds: Maximum time to wait for Earth Engine operations (not used, kept for compatibility)
        
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
        
        # Get all location data
        location_data = extract_all_risk_data(lat, lon, debug=False)
        
        # Extract relevant data for risk calculation
        fire_history = location_data.get("fire_history", {})
        current_conditions = location_data.get("current_conditions", {})
        vegetation = current_conditions.get("vegetation", {})
        
        # Get NDVI
        ndvi = None
        if "NDVI" in vegetation and "NDVI_mean" in vegetation["NDVI"]:
            ndvi = vegetation["NDVI"]["NDVI_mean"]
        
        # Get fire count
        fire_count = None
        if "total_fires_in_period" in fire_history:
            fire_count = fire_history["total_fires_in_period"]
        
        # Get temperature data (convert from Kelvin to Celsius)
        temp_data = None
        surface_temp = current_conditions.get("surface_temperature", {})
        if "AvgSurfT_inst_mean" in surface_temp and surface_temp["AvgSurfT_inst_mean"]:
            temp_k = surface_temp["AvgSurfT_inst_mean"]
            temp_c = temp_k - 273.15
            # Use current temp as both current and historical (simplified)
            temp_data = (temp_c, temp_c)
        
        # Calculate risk score (simplified version)
        score = 0.0
        explanations = []
        
        # Fire history (30% weight)
        if fire_count is not None:
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
            score += fire_score * 0.30
            explanations.append(fire_expl)
        else:
            score += 5.0 * 0.30
            explanations.append("Historical fire data unavailable")
        
        # Vegetation/NDVI (25% weight)
        if ndvi is not None:
            if ndvi < 0.3:
                veg_score = ndvi / 0.3 * 3
                veg_expl = "Low vegetation density"
            elif ndvi < 0.6:
                veg_score = 3 + ((ndvi - 0.3) / 0.3) * 4
                veg_expl = "Moderate vegetation density"
            else:
                veg_score = 7 + min(3, ((ndvi - 0.6) / 0.4) * 3)
                veg_expl = "High vegetation density (high fuel load)"
            score += veg_score * 0.25
            explanations.append(veg_expl)
        else:
            score += 5.0 * 0.25
            explanations.append("Vegetation data unavailable")
        
        # Temperature (20% weight) - simplified
        if temp_data:
            score += 5.0 * 0.20  # Default moderate
            explanations.append("Temperature data available")
        else:
            score += 5.0 * 0.20
            explanations.append("Temperature data unavailable")
        
        # Precipitation (15% weight) - not available in current data
        score += 5.0 * 0.15
        explanations.append("Precipitation data unavailable")
        
        # Elevation (10% weight) - not available in current data
        score += 5.0 * 0.10
        explanations.append("Elevation data unavailable")
        
        explanation = ". ".join(explanations[:3])
        if len(explanations) > 3:
            explanation += "."
        
        # Track data sources
        data_sources = {
            "ndvi": ndvi is not None,
            "temperature": temp_data is not None,
            "precipitation": False,
            "historical_fires": fire_count is not None,
            "elevation": False
        }
        
        logger.info(f"Wildfire risk calculated: {score}/10")
        
        return {
            "score": round(score, 1),
            "explanation": explanation,
            "data_sources": data_sources,
            "raw_data": {
                "ndvi": ndvi,
                "temperature": temp_data,
                "precipitation": None,
                "fire_count": fire_count,
                "elevation": None
            }
        }
        
    except Exception as e:
        logger.error(f"Error calculating wildfire risk with Earth Engine: {e}")
        logger.debug(traceback.format_exc())
        return None
