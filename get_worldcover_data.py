"""
ESA WorldCover Datenabfrage für einen 10x10m Square
Dieses Script extrahiert Landcover-Daten für einen fest definierten Test-Square.
"""
import ee
import json
import time


# ============================================================================
# HARDCODED TEST SQUARE - Wird für alle zukünftigen Tests verwendet
# ============================================================================
# Koordinaten: Zentrum des Squares (München, Deutschland)
# Ein 10x10m Square um diesen Punkt
TEST_SQUARE_CENTER_LON = 11.5761  # Längengrad
TEST_SQUARE_CENTER_LAT = 48.1374  # Breitengrad

# Größe des Squares in Metern
SQUARE_SIZE_METERS = 10  # 10m x 10m

# ============================================================================
# HARDCODED TEST DATE - Wird für alle zukünftigen Tests verwendet
# ============================================================================
# Ein spezifisches Datum für Tests (muss verfügbar sein in den Datensätzen)
# GLDAS V20 geht nur bis 2014, daher verwenden wir ein Datum aus diesem Zeitraum
TEST_DATE = "2010-06-01"  # Format: YYYY-MM-DD (verfügbar in GLDAS)
FIRE_HISTORY_START_DATE = "2010-01-01"  # Startdatum für historische Branddaten


def get_test_square():
    """
    Erstellt einen 10x10m Square um den hardcodierten Test-Punkt.
    
    Returns:
        ee.Geometry.Rectangle: Ein 10x10m Square als Rectangle
    """
    center = ee.Geometry.Point([TEST_SQUARE_CENTER_LON, TEST_SQUARE_CENTER_LAT])
    
    # Konvertiere Meter zu Grad (ungefähr)
    # 1 Grad ≈ 111,320 Meter (am Äquator)
    # Bei 48° Breite: 1 Grad ≈ 111,320 * cos(48°) ≈ 74,500 Meter
    meters_per_degree_lat = 111320  # Breitengrad ist konstant
    meters_per_degree_lon = 111320 * 0.669  # cos(48°) ≈ 0.669
    
    # Halbe Größe in Grad
    half_size_lat = (SQUARE_SIZE_METERS / 2) / meters_per_degree_lat
    half_size_lon = (SQUARE_SIZE_METERS / 2) / meters_per_degree_lon
    
    # Erstelle Rectangle um den Mittelpunkt
    square = ee.Geometry.Rectangle([
        TEST_SQUARE_CENTER_LON - half_size_lon,  # West
        TEST_SQUARE_CENTER_LAT - half_size_lat,  # South
        TEST_SQUARE_CENTER_LON + half_size_lon,  # East
        TEST_SQUARE_CENTER_LAT + half_size_lat   # North
    ])
    
    return square


def load_worldcover():
    """
    Lädt das ESA WorldCover Dataset.
    
    Returns:
        ee.Image: Das erste Bild aus der WorldCover ImageCollection
    """
    dataset = ee.ImageCollection("ESA/WorldCover/v100").first()
    return dataset


def get_landcover_classes():
    """
    Gibt ein Dictionary mit den Landcover-Klassen zurück.
    
    Returns:
        dict: Mapping von Klassenwert zu Beschreibung
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


def extract_square_data(image, square):
    """
    Extrahiert alle Pixel-Daten für den Square.
    
    Args:
        image: ee.Image - Das WorldCover Bild
        square: ee.Geometry - Der 10x10m Square
    
    Returns:
        dict: Dictionary mit extrahierten Daten
    """
    # Extrahiere alle Pixel-Werte im Square
    # Bei 10m Auflösung und 10x10m Square = 1 Pixel (theoretisch)
    # Aber wir extrahieren alle Pixel für Genauigkeit
    samples = image.sample(
        region=square,
        scale=10,  # 10m Auflösung (entspricht der Dataset-Auflösung)
        numPixels=100,  # Maximal 100 Pixel (sollte für 10x10m ausreichen)
        geometries=True  # Behalte Geometrie-Informationen
    )
    
    # Konvertiere zu FeatureCollection und hole die Daten
    features = samples.getInfo()
    
    return features


def get_square_statistics(image, square):
    """
    Berechnet Statistiken für den Square.
    
    Args:
        image: ee.Image - Das WorldCover Bild
        square: ee.Geometry - Der 10x10m Square
    
    Returns:
        dict: Dictionary mit Statistiken
    """
    # Histogramm der Landcover-Klassen
    histogram = image.select('Map').reduceRegion(
        reducer=ee.Reducer.frequencyHistogram(),
        geometry=square,
        scale=10,  # 10m Auflösung
        maxPixels=1e9
    )
    
    stats = histogram.getInfo()
    
    return stats


# ============================================================================
# HILFSFUNKTIONEN für generische Datenabfragen
# ============================================================================

def extract_statistics(image, square, band_name, scale=1000, debug=False):
    """
    Generische Funktion für reduceRegion Statistiken.
    
    Args:
        image: ee.Image - Das Bild
        square: ee.Geometry - Der Square
        band_name: str - Name des Bands
        scale: float - Auflösung in Metern (Default: 1000m für GLDAS)
        debug: bool - Wenn True, werden Debug-Infos ausgegeben
    
    Returns:
        dict: Dictionary mit Statistiken (mean, min, max, stdDev)
    """
    stats = image.select(band_name).reduceRegion(
        reducer=ee.Reducer.mean().combine(
            reducer2=ee.Reducer.minMax(),
            sharedInputs=True
        ).combine(
            reducer2=ee.Reducer.stdDev(),
            sharedInputs=True
        ),
        geometry=square,
        scale=scale,
        maxPixels=1e9,
        bestEffort=True  # Beschleunigt die Abfrage
    )
    
    result = stats.getInfo()
    if debug:
        print(f"\n      DEBUG [{band_name}]: {result}")
    return result


def extract_multiple_statistics(image, square, band_names, scale=1000, debug=False):
    """
    Extrahiert Statistiken für mehrere Bands gleichzeitig (schneller).
    
    Args:
        image: ee.Image - Das Bild
        square: ee.Geometry - Der Square
        band_names: list - Liste von Band-Namen
        scale: float - Auflösung in Metern
        debug: bool - Wenn True, werden Debug-Infos ausgegeben
    
    Returns:
        dict: Dictionary mit Statistiken für alle Bands
    """
    # Prüfe ob die Bands existieren
    available_bands = image.bandNames().getInfo()
    if debug:
        print(f"      Verfügbare Bands: {available_bands}")
        missing_bands = [b for b in band_names if b not in available_bands]
        if missing_bands:
            print(f"      Warnung: Fehlende Bands: {missing_bands}")
    
    # Verwende nur verfügbare Bands
    valid_bands = [b for b in band_names if b in available_bands]
    if not valid_bands:
        if debug:
            print(f"      Fehler: Keine der angeforderten Bands ist verfügbar!")
        return {}
    
    # Für sehr kleine Geometrien (wie 10x10m Square): Verwende sample() am Mittelpunkt
    # statt reduceRegion, da der Square viel kleiner ist als die Pixel-Auflösung
    center = square.centroid()
    
    # Extrahiere Werte am Mittelpunkt
    sample = image.select(valid_bands).sample(
        region=center,
        scale=scale,
        numPixels=1
    )
    
    # Hole die Werte
    sample_info = sample.getInfo()
    
    result = {}
    if sample_info and 'features' in sample_info and len(sample_info['features']) > 0:
        props = sample_info['features'][0].get('properties', {})
        for band in valid_bands:
            value = props.get(band)
            if value is not None:
                # Für sample() gibt es nur einen Wert, verwende diesen für mean/min/max
                result[f'{band}_mean'] = value
                result[f'{band}_min'] = value
                result[f'{band}_max'] = value
    
    if debug:
        print(f"\n      DEBUG [Bands: {', '.join(valid_bands)}]: {result}")
        # Prüfe auf null/None Werte
        null_values = {k: v for k, v in result.items() if v is None}
        if null_values:
            print(f"      Warnung: Null-Werte gefunden: {list(null_values.keys())}")
    
    return result


def get_latest_image(collection, date, debug=False):
    """
    Holt das neueste verfügbare Bild vor/nach einem Datum.
    
    Args:
        collection: ee.ImageCollection - Die ImageCollection
        date: str - Datum im Format "YYYY-MM-DD"
        debug: bool - Wenn True, werden Debug-Infos ausgegeben
    
    Returns:
        ee.Image: Das neueste Bild
    
    Raises:
        Exception: Wenn kein Bild gefunden wird
    """
    # Filtere nach Datum (nehme das neueste Bild vor dem angegebenen Datum)
    # Füge einen Tag hinzu, um das angegebene Datum einzuschließen
    from datetime import datetime, timedelta
    date_obj = datetime.strptime(date, "%Y-%m-%d")
    end_date = (date_obj + timedelta(days=1)).strftime("%Y-%m-%d")
    
    filtered = collection.filterDate('2000-01-01', end_date).sort('system:time_start', False)
    
    # Prüfe ob Bilder vorhanden sind
    if debug:
        count = filtered.size().getInfo()
        print(f"      DEBUG: {count} Bilder gefunden für Datum <= {date}")
        if count > 0:
            first_image_info = filtered.first().getInfo()
            if first_image_info and 'properties' in first_image_info:
                img_date = first_image_info['properties'].get('system:time_start')
                if img_date:
                    img_date_str = datetime.fromtimestamp(img_date / 1000).strftime("%Y-%m-%d %H:%M:%S")
                    print(f"      DEBUG: Neuestes Bild vom: {img_date_str}")
    
    return filtered.first()


# ============================================================================
# GLDAS DATENSATZ - Temperatur, Bodenfeuchte, Bodentemperatur, Wind
# ============================================================================

def load_gldas_data(date=TEST_DATE, debug=False):
    """
    Lädt GLDAS-2.0 Daten für ein bestimmtes Datum.
    GLDAS V20 geht nur bis 2014, daher wird das neueste verfügbare Bild verwendet.
    
    Args:
        date: str - Datum im Format "YYYY-MM-DD" (Default: TEST_DATE)
        debug: bool - Wenn True, werden Debug-Infos ausgegeben
    
    Returns:
        ee.Image: Das neueste verfügbare GLDAS Bild
    """
    print(f"      → Suche GLDAS-Bild für {date}...", end="", flush=True)
    collection = ee.ImageCollection("NASA/GLDAS/V20/NOAH/G025/T3H")
    
    # Filtere nach dem spezifischen Datum (GLDAS hat 3-stündliche Daten)
    from datetime import datetime, timedelta
    date_obj = datetime.strptime(date, "%Y-%m-%d")
    start_date = date_obj.strftime("%Y-%m-%d")
    end_date = (date_obj + timedelta(days=1)).strftime("%Y-%m-%d")
    
    # Filtere nach Datum und nimm das erste verfügbare Bild
    filtered = collection.filterDate(start_date, end_date)
    image = filtered.first()
    
    if debug:
        count = filtered.size().getInfo()
        print(f"\n      DEBUG: {count} Bilder gefunden für {start_date}")
    
    print(" gefunden", end="", flush=True)
    return image


def get_all_gldas_data(square, date=TEST_DATE, debug=True):
    """
    Extrahiert alle GLDAS-Daten in einer einzigen Abfrage (schneller).
    
    Args:
        square: ee.Geometry - Der 10x10m Square
        date: str - Datum im Format "YYYY-MM-DD" (Default: TEST_DATE)
        debug: bool - Wenn True, werden Debug-Infos ausgegeben
    
    Returns:
        dict: Dictionary mit allen GLDAS-Statistiken
    """
    print(f"\n    → Lade GLDAS-Daten für {date}...")
    start_time = time.time()
    
    load_start = time.time()
    image = load_gldas_data(date, debug=debug)
    load_elapsed = time.time() - load_start
    print(f"      (Bild geladen in {load_elapsed:.1f}s)")
    
    # Prüfe ob das Bild gültig ist
    try:
        image_info = image.getInfo()
        if not image_info or 'bands' not in image_info:
            raise Exception("Bild ist leer oder ungültig")
    except Exception as e:
        if debug:
            print(f"      Fehler beim Prüfen des Bildes: {e}")
        return {
            'surface_temperature': {'error': str(e)},
            'soil_moisture': {'error': str(e)},
            'soil_temperature': {'error': str(e)},
            'wind_speed': {'error': str(e)}
        }
    
    # Extrahiere alle Bands gleichzeitig
    print(f"      → Extrahiere Statistiken...", end="", flush=True)
    extract_start = time.time()
    band_names = ['AvgSurfT_inst', 'SoilMoi0_10cm_inst', 'SoilTMP0_10cm_inst', 'Wind_f_inst']
    # GLDAS Auflösung: 0.25° ≈ 25km, verwende 25000m als scale
    # Für einen sehr kleinen Square könnte es sein, dass wir einen größeren Scale brauchen
    all_stats = extract_multiple_statistics(image, square, band_names, scale=25000, debug=debug)
    extract_elapsed = time.time() - extract_start
    print(f" ({extract_elapsed:.1f}s)")
    
    elapsed = time.time() - start_time
    print(f"    ✓ GLDAS-Daten komplett in {elapsed:.1f}s")
    
    # Strukturiere die Daten - verwende get() mit Default None
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
    
    if debug:
        print(f"      Response-Struktur: {list(result.keys())}")
        # Prüfe auf null-Werte
        has_data = False
        for key, value in result.items():
            if value and isinstance(value, dict):
                non_null = {k: v for k, v in value.items() if v is not None}
                if non_null:
                    has_data = True
                    print(f"        {key}: {list(non_null.keys())} (Werte vorhanden)")
                else:
                    print(f"        {key}: Alle Werte sind null")
        if not has_data:
            print(f"      Warnung: Keine GLDAS-Daten gefunden! Möglicherweise:")
            print(f"        - Falsches Datum (keine Daten verfügbar)")
            print(f"        - Square zu klein für 25km Auflösung")
            print(f"        - Bands haben andere Namen")
    
    return result


def get_surface_temperature(square, date=TEST_DATE):
    """
    Extrahiert Oberflächentemperatur für den Square.
    DEPRECATED: Verwende get_all_gldas_data() für bessere Performance.
    """
    image = load_gldas_data(date)
    stats = extract_statistics(image, square, 'AvgSurfT_inst', scale=25000)
    return stats


def get_soil_moisture(square, date=TEST_DATE):
    """
    Extrahiert Bodenfeuchte für den Square.
    DEPRECATED: Verwende get_all_gldas_data() für bessere Performance.
    """
    image = load_gldas_data(date)
    stats = extract_statistics(image, square, 'SoilMoi0_10cm_inst', scale=25000)
    return stats


def get_soil_temperature(square, date=TEST_DATE):
    """
    Extrahiert Bodentemperatur für den Square.
    DEPRECATED: Verwende get_all_gldas_data() für bessere Performance.
    """
    image = load_gldas_data(date)
    stats = extract_statistics(image, square, 'SoilTMP0_10cm_inst', scale=25000)
    return stats


def get_wind_speed(square, date=TEST_DATE):
    """
    Extrahiert Windgeschwindigkeit für den Square.
    DEPRECATED: Verwende get_all_gldas_data() für bessere Performance.
    """
    image = load_gldas_data(date)
    stats = extract_statistics(image, square, 'Wind_f_inst', scale=25000)
    return stats


# ============================================================================
# MODIS VEGETATIONSINDIZES - NDVI/EVI für Vegetationsfeuchte
# ============================================================================

def load_modis_ndvi(date=TEST_DATE):
    """
    Lädt MODIS Vegetationsindizes für ein bestimmtes Datum.
    Verwendet die aktuelle Version MODIS/061/MOD13A1 statt der deprecated Version.
    
    Args:
        date: str - Datum im Format "YYYY-MM-DD" (Default: TEST_DATE)
    
    Returns:
        ee.Image: Das neueste verfügbare MODIS NDVI Bild
    """
    # Verwende die aktuelle Version statt MODIS/006/MOD13A1
    collection = ee.ImageCollection("MODIS/061/MOD13A1")
    return get_latest_image(collection, date)


def get_vegetation_indices(square, date=TEST_DATE, debug=True):
    """
    Extrahiert Vegetationsindizes (NDVI, EVI) für den Square.
    
    Args:
        square: ee.Geometry - Der 10x10m Square
        date: str - Datum im Format "YYYY-MM-DD" (Default: TEST_DATE)
        debug: bool - Wenn True, werden Debug-Infos ausgegeben
    
    Returns:
        dict: Dictionary mit NDVI und EVI Statistiken
    """
    print(f"    → Lade MODIS Vegetationsindizes für {date}...", end="", flush=True)
    start_time = time.time()
    
    try:
        image = load_modis_ndvi(date)
        # MODIS Auflösung: 500m - für 10x10m Square verwenden wir sample() am Mittelpunkt
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
                    # MODIS NDVI/EVI sind skaliert (0-10000), teile durch 10000
                    scaled_value = value / 10000.0 if value > 1 else value
                    all_stats[f'{band}_mean'] = scaled_value
                    all_stats[f'{band}_min'] = scaled_value
                    all_stats[f'{band}_max'] = scaled_value
        
        if debug:
            print(f"\n      DEBUG [MODIS sample]: {all_stats}")
    except Exception as e:
        if debug:
            print(f"      Fehler: {e}")
        return {'NDVI': {'error': str(e)}, 'EVI': {'error': str(e)}}
    
    elapsed = time.time() - start_time
    print(f" ✓ ({elapsed:.1f}s)")
    
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
    
    if debug:
        has_data = False
        for key, value in result.items():
            if value and isinstance(value, dict):
                if any(v is not None for v in value.values()):
                    has_data = True
                    break
        if not has_data:
            print(f"      Warnung: Keine MODIS-Daten gefunden!")
        else:
            print(f"      Response: {result}")
    
    return result


# ============================================================================
# FIRMS - Historische Waldbrände
# ============================================================================

def get_historical_fires(square, start_date=FIRE_HISTORY_START_DATE, end_date=TEST_DATE, debug=True):
    """
    Prüft, ob jemals ein Waldbrand in der Vergangenheit in diesem Pixel war.
    FIRMS ist eine ImageCollection, nicht FeatureCollection!
    Jeder aktive Brandort stellt den Schwerpunkt eines 1-km-Pixels dar.
    
    Args:
        square: ee.Geometry - Der 10x10m Square
        start_date: str - Startdatum im Format "YYYY-MM-DD" (Default: FIRE_HISTORY_START_DATE)
        end_date: str - Enddatum im Format "YYYY-MM-DD" (Default: TEST_DATE)
        debug: bool - Wenn True, werden Debug-Infos ausgegeben
    
    Returns:
        dict: Dictionary mit Brandstatistiken
    """
    print(f"    → Prüfe FIRMS Branddaten ({start_date} bis {end_date})...", end="", flush=True)
    start_time = time.time()
    
    # FIRMS ist eine ImageCollection, nicht FeatureCollection!
    firms = ee.ImageCollection('FIRMS')
    
    # Filtere nach Datum
    filtered = firms.filterDate(start_date, end_date)
    
    # Verwende den Mittelpunkt des Squares
    # FIRMS hat 1km Auflösung, daher prüfen wir ob der 1km-Pixel, der diesen Punkt enthält, jemals gebrannt hat
    center = square.centroid()
    
    # Erstelle ein Mosaik aller Bilder im Zeitraum und extrahiere T21 Band (Brightness Temperature)
    # Pixel mit Werten > 0 sind Brände
    fires_mosaic = filtered.select('T21').mosaic()
    
    # Prüfe ob es jemals einen Brand in diesem Pixel gab (T21 > 0)
    # Verwende sample() am Mittelpunkt um den Pixel-Wert zu bekommen
    fire_sample = fires_mosaic.sample(
        region=center,
        scale=1000,  # FIRMS hat 1km Auflösung
        numPixels=1
    )
    
    fire_sample_info = fire_sample.getInfo()
    has_fire = False
    fire_value = None
    
    if fire_sample_info and 'features' in fire_sample_info and len(fire_sample_info['features']) > 0:
        props = fire_sample_info['features'][0].get('properties', {})
        fire_value = props.get('T21')
        has_fire = fire_value is not None and fire_value > 0
    
    # Zähle auch die Gesamtanzahl der Brand-Pixel im Zeitraum (für zusätzliche Info)
    fire_mask = fires_mosaic.gt(0)
    fire_count = fire_mask.reduceRegion(
        reducer=ee.Reducer.sum(),
        geometry=center.buffer(500),  # 500m Buffer um sicherzustellen, dass wir den Pixel erfassen
        scale=1000,
        maxPixels=1e9,
        bestEffort=True
    )
    
    count_value = fire_count.getInfo().get('T21', 0)
    
    # Berechne Jahre zwischen start und end
    from datetime import datetime
    start = datetime.strptime(start_date, "%Y-%m-%d")
    end = datetime.strptime(end_date, "%Y-%m-%d")
    years = (end - start).days / 365.25
    
    fires_per_year = count_value / years if years > 0 else 0.0
    
    # Hole letztes Branddatum - finde das neueste Bild mit Bränden
    last_fire_date = None
    if has_fire:
        try:
            # Sortiere nach Datum (neueste zuerst) und prüfe ob es Brände gibt
            sorted_collection = filtered.sort('system:time_start', False)
            collection_size = filtered.size().getInfo()
            # Prüfe die ersten Bilder
            for i in range(min(20, collection_size)):
                image = ee.Image(sorted_collection.toList(1, i).get(0))
                # Prüfe ob es Brände in diesem Bild am Mittelpunkt gibt
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
                        # Hole das Datum dieses Bildes
                        date_prop = image.get('system:time_start').getInfo()
                        if date_prop:
                            last_fire_date = datetime.fromtimestamp(date_prop / 1000).strftime("%Y-%m-%d")
                            break
        except Exception as e:
            if debug:
                print(f"      Warnung: Konnte letztes Branddatum nicht abrufen: {e}")
    
    elapsed = time.time() - start_time
    fire_status = "Brand gefunden" if has_fire else "Kein Brand"
    print(f" ✓ ({elapsed:.1f}s) - {fire_status}")
    
    if debug:
        if has_fire:
            print(f"      Brand-Pixel-Wert (T21): {fire_value}")
        print(f"      Gesamtanzahl Brand-Pixel im Zeitraum: {int(count_value)}")
    
    result = {
        'has_fire': has_fire,  # Boolean: War jemals ein Brand in diesem Pixel?
        'last_fire_date': last_fire_date,  # Datum des letzten Brandes oder null
        'total_fires_in_period': int(count_value),  # Anzahl Brand-Pixel im Zeitraum
        'fires_per_year': round(fires_per_year, 2)  # Durchschnittliche Brände pro Jahr
    }
    
    if debug:
        print(f"      Response: {result}")
    
    return result


# ============================================================================
# GLCF - Wasserflächen (Binnengewässer)
# ============================================================================

def load_water_mask():
    """
    Lädt GLCF Wasserflächen-Maske.
    GLCF/GLS_WATER ist eine ImageCollection, nicht ein einzelnes Image.
    
    Returns:
        ee.Image: Das Wasserflächen-Bild (erstes Bild aus der Collection)
    """
    # GLCF/GLS_WATER ist eine ImageCollection, nimm das erste Bild
    collection = ee.ImageCollection("GLCF/GLS_WATER")
    return collection.first()


def get_water_bodies(square, debug=True):
    """
    Extrahiert Wasserflächen-Informationen für den Square.
    
    Args:
        square: ee.Geometry - Der 10x10m Square
        debug: bool - Wenn True, werden Debug-Infos ausgegeben
    
    Returns:
        dict: Dictionary mit Wasserflächen-Statistiken
    """
    print(f"    → Lade GLCF Wasserflächen-Daten...", end="", flush=True)
    start_time = time.time()
    
    image = load_water_mask()
    
    # Berechne Anteil Wasserfläche im Square
    # GLCF Auflösung: 30m
    water_stats = image.select('water').reduceRegion(
        reducer=ee.Reducer.frequencyHistogram(),
        geometry=square,
        scale=30,
        maxPixels=1e9,
        bestEffort=True
    )
    
    stats = water_stats.getInfo()
    if debug:
        print(f"\n      DEBUG [water_stats]: {stats}")
    
    # Berechne Wasseranteil
    water_coverage = 0.0
    if 'water' in stats and stats['water']:
        histogram = stats['water']
        total_pixels = sum(float(v) for v in histogram.values())
        water_pixels = histogram.get('1', 0)  # 1 = Wasser
        if total_pixels > 0:
            water_coverage = (float(water_pixels) / total_pixels) * 100.0
    
    # Prüfe auch in der Nähe (100m Radius)
    center = square.centroid()
    buffer = center.buffer(100)  # 100m Radius
    
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
    
    elapsed = time.time() - start_time
    print(f" ✓ ({elapsed:.1f}s)")
    
    result = {
        'water_coverage_percent': water_coverage,
        'nearby_water_coverage_percent': nearby_water_coverage
    }
    
    if debug:
        print(f"      Response: {result}")
    
    return result


def print_square_info(square):
    """Gibt Informationen über den Test-Square aus."""
    print("\n" + "=" * 60)
    print("Test Square Informationen")
    print("=" * 60)
    print(f"Zentrum: {TEST_SQUARE_CENTER_LAT}, {TEST_SQUARE_CENTER_LON}")
    print(f"Größe: {SQUARE_SIZE_METERS}m x {SQUARE_SIZE_METERS}m")
    
    # Hole Bounds des Squares
    bounds = square.bounds().getInfo()
    coords = bounds['coordinates'][0]
    print(f"Bounds: {coords}")


def print_extracted_data(features, stats):
    """Gibt die extrahierten Daten formatiert aus."""
    print("\n" + "=" * 60)
    print("Extrahierten Daten")
    print("=" * 60)
    
    # Anzahl der Pixel
    num_pixels = len(features.get('features', []))
    print(f"\nAnzahl Pixel im Square: {num_pixels}")
    
    # Landcover-Klassen
    classes = get_landcover_classes()
    
    # Extrahiere alle Landcover-Werte
    landcover_values = []
    for feature in features.get('features', []):
        props = feature.get('properties', {})
        value = props.get('Map')
        if value is not None:
            landcover_values.append(value)
    
    if landcover_values:
        print(f"\nLandcover-Werte im Square:")
        # Zähle Vorkommen jeder Klasse
        from collections import Counter
        value_counts = Counter(landcover_values)
        
        for value, count in sorted(value_counts.items()):
            class_name = classes.get(value, "Unbekannt")
            percentage = (count / len(landcover_values)) * 100
            print(f"  Klasse {value:3d} ({class_name:30s}): {count:2d} Pixel ({percentage:5.1f}%)")
    
    # Statistiken aus reduceRegion
    if stats and 'Map' in stats:
        print(f"\nStatistiken (reduceRegion):")
        histogram = stats['Map']
        total_pixels = sum(int(v) for v in histogram.values())
        
        for value_str, count in sorted(histogram.items(), key=lambda x: int(x[0])):
            value = int(value_str)
            count_int = int(count)
            class_name = classes.get(value, "Unbekannt")
            percentage = (count_int / total_pixels) * 100 if total_pixels > 0 else 0
            print(f"  Klasse {value:3d} ({class_name:30s}): {count_int:2d} Pixel ({percentage:5.1f}%)")
    elif stats:
        print(f"\nStatistiken (reduceRegion): Keine Daten verfügbar")
        print(f"  Stats keys: {list(stats.keys())}")


def print_risk_data(all_data):
    """Gibt alle Wildfire-Risiko-Daten formatiert aus."""
    print("\n" + "=" * 60)
    print("Wildfire Risk Score Daten")
    print("=" * 60)
    
    # Square Info
    square_info = all_data.get("square_info", {})
    print(f"\nTest-Datum: {square_info.get('date', 'N/A')}")
    
    # WorldCover Daten
    worldcover = all_data.get("worldcover", {})
    if "error" not in worldcover and "features" in worldcover:
        features = worldcover.get("features", {})
        stats = worldcover.get("statistics", {})
        print_extracted_data(features, stats)
    elif "error" in worldcover:
        print(f"\nWorldCover: Fehler - {worldcover['error']}")
    
    # Historische Brände
    fire_history = all_data.get("fire_history", {})
    if "error" not in fire_history:
        print("\n" + "-" * 60)
        print("Historische Brände (FIRMS)")
        print("-" * 60)
        has_fire = fire_history.get('has_fire', False)
        print(f"  Brand in diesem Pixel: {'Ja' if has_fire else 'Nein'}")
        if has_fire:
            print(f"  Letztes Branddatum: {fire_history.get('last_fire_date', 'Unbekannt')}")
        print(f"  Gesamtanzahl Brand-Pixel im Zeitraum: {fire_history.get('total_fires_in_period', 0)}")
        print(f"  Brände pro Jahr: {fire_history.get('fires_per_year', 0.0):.2f}")
    else:
        print(f"\nFIRMS: Fehler - {fire_history['error']}")
    
    # Aktuelle Bedingungen
    current = all_data.get("current_conditions", {})
    print("\n" + "-" * 60)
    print("Aktuelle Bedingungen")
    print("-" * 60)
    
    # Oberflächentemperatur
    if "error" not in current.get("surface_temperature", {}):
        temp = current.get("surface_temperature", {})
        if temp:
            print(f"\nOberflächentemperatur:")
            print(f"  Mittelwert: {temp.get('AvgSurfT_inst_mean', 'N/A')} K")
            print(f"  Min: {temp.get('AvgSurfT_inst_min', 'N/A')} K")
            print(f"  Max: {temp.get('AvgSurfT_inst_max', 'N/A')} K")
    else:
        print(f"\nOberflächentemperatur: Fehler")
    
    # Bodenfeuchte
    if "error" not in current.get("soil_moisture", {}):
        moisture = current.get("soil_moisture", {})
        if moisture:
            print(f"\nBodenfeuchte (0-10cm):")
            print(f"  Mittelwert: {moisture.get('SoilMoi0_10cm_inst_mean', 'N/A')} kg/m²")
    else:
        print(f"\nBodenfeuchte: Fehler")
    
    # Bodentemperatur
    if "error" not in current.get("soil_temperature", {}):
        soil_temp = current.get("soil_temperature", {})
        if soil_temp:
            print(f"\nBodentemperatur (0-10cm):")
            print(f"  Mittelwert: {soil_temp.get('SoilTMP0_10cm_inst_mean', 'N/A')} K")
    else:
        print(f"\nBodentemperatur: Fehler")
    
    # Windgeschwindigkeit
    if "error" not in current.get("wind_speed", {}):
        wind = current.get("wind_speed", {})
        if wind:
            print(f"\nWindgeschwindigkeit:")
            print(f"  Mittelwert: {wind.get('Wind_f_inst_mean', 'N/A')} m/s")
            print(f"  Max: {wind.get('Wind_f_inst_max', 'N/A')} m/s")
    else:
        print(f"\nWindgeschwindigkeit: Fehler")
    
    # Vegetationsindizes
    vegetation = current.get("vegetation", {})
    if "error" not in vegetation:
        print(f"\nVegetationsindizes:")
        if "NDVI" in vegetation and vegetation["NDVI"]:
            ndvi = vegetation["NDVI"]
            print(f"  NDVI Mittelwert: {ndvi.get('NDVI_mean', 'N/A')}")
        if "EVI" in vegetation and vegetation["EVI"]:
            evi = vegetation["EVI"]
            print(f"  EVI Mittelwert: {evi.get('EVI_mean', 'N/A')}")
    else:
        print(f"\nVegetationsindizes: Fehler")
    
    # Wasserflächen
    water_coverage = current.get("water_coverage")
    nearby_water = current.get("nearby_water_coverage")
    if water_coverage is not None:
        print(f"\nWasserflächen:")
        print(f"  Wasseranteil im Square: {water_coverage:.2f}%")
        print(f"  Wasseranteil in 100m Radius: {nearby_water:.2f}%")
    else:
        print(f"\nWasserflächen: Fehler")


def extract_all_risk_data(square, date=TEST_DATE, fire_history_start=FIRE_HISTORY_START_DATE):
    """
    Sammelt alle Wildfire-Risiko-Daten für den Square.
    
    Args:
        square: ee.Geometry - Der 10x10m Square
        date: str - Datum im Format "YYYY-MM-DD" (Default: TEST_DATE)
        fire_history_start: str - Startdatum für historische Brände (Default: FIRE_HISTORY_START_DATE)
    
    Returns:
        dict: Dictionary mit allen extrahierten Daten
    """
    total_start_time = time.time()
    all_data = {
        "square_info": {
            "center_lon": TEST_SQUARE_CENTER_LON,
            "center_lat": TEST_SQUARE_CENTER_LAT,
            "size_meters": SQUARE_SIZE_METERS,
            "date": date
        },
        "worldcover": {},
        "fire_history": {},
        "current_conditions": {}
    }
    
    print(f"\nExtrahiere Daten für {date}...")
    
    # WorldCover Daten (bestehend)
    print("  [1/5] WorldCover Landcover-Daten...", end="", flush=True)
    try:
        start_time = time.time()
        worldcover = load_worldcover()
        features = extract_square_data(worldcover, square)
        stats = get_square_statistics(worldcover, square)
        elapsed = time.time() - start_time
        print(f" ✓ ({elapsed:.1f}s)")
        print(f"      Response: {len(features.get('features', []))} Features, Stats: {list(stats.keys()) if stats else 'None'}")
        all_data["worldcover"] = {
            "features": features,
            "statistics": stats
        }
    except Exception as e:
        print(f" ✗ Fehler: {e}")
        all_data["worldcover"] = {"error": str(e)}
    
    # Historische Brände
    print("  [2/5] Historische Brände (FIRMS)...", end="", flush=True)
    try:
        fire_data = get_historical_fires(square, fire_history_start, date)
        all_data["fire_history"] = fire_data
    except Exception as e:
        print(f" ✗ Fehler: {e}")
        all_data["fire_history"] = {"error": str(e)}
    
    # Aktuelle Bedingungen
    current_conditions = {}
    
    # GLDAS-Daten (alle auf einmal für bessere Performance)
    print("  [3/5] GLDAS-Daten (Temperatur, Bodenfeuchte, Wind)...", end="", flush=True)
    try:
        gldas_data = get_all_gldas_data(square, date)
        current_conditions["surface_temperature"] = gldas_data["surface_temperature"]
        current_conditions["soil_moisture"] = gldas_data["soil_moisture"]
        current_conditions["soil_temperature"] = gldas_data["soil_temperature"]
        current_conditions["wind_speed"] = gldas_data["wind_speed"]
    except Exception as e:
        print(f" ✗ Fehler: {e}")
        current_conditions["surface_temperature"] = {"error": str(e)}
        current_conditions["soil_moisture"] = {"error": str(e)}
        current_conditions["soil_temperature"] = {"error": str(e)}
        current_conditions["wind_speed"] = {"error": str(e)}
    
    # Vegetationsindizes
    print("  [4/5] MODIS Vegetationsindizes...", end="", flush=True)
    try:
        vegetation = get_vegetation_indices(square, date)
        current_conditions["vegetation"] = vegetation
    except Exception as e:
        print(f" ✗ Fehler: {e}")
        current_conditions["vegetation"] = {"error": str(e)}
    
    # Wasserflächen
    print("  [5/5] Wasserflächen (GLCF)...", end="", flush=True)
    try:
        water = get_water_bodies(square)
        current_conditions["water_coverage"] = water["water_coverage_percent"]
        current_conditions["nearby_water_coverage"] = water["nearby_water_coverage_percent"]
    except Exception as e:
        print(f" ✗ Fehler: {e}")
        current_conditions["water_coverage"] = None
        current_conditions["nearby_water_coverage"] = None
    
    all_data["current_conditions"] = current_conditions
    
    total_elapsed = time.time() - total_start_time
    print(f"\n✓ Alle Daten extrahiert in {total_elapsed:.1f}s")
    
    return all_data


def save_data_to_json(all_data, output_file="square_data.json"):
    """
    Speichert die extrahierten Daten als JSON.
    
    Args:
        all_data: Dictionary mit allen extrahierten Daten
        output_file: Pfad zur Ausgabedatei
    """
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(all_data, f, indent=2, ensure_ascii=False)
    
    print(f"\n✓ Daten gespeichert in: {output_file}")


def initialize_earth_engine():
    """
    Initialisiert Earth Engine (versucht verschiedene Methoden).
    
    Returns:
        bool: True bei Erfolg, False bei Fehler
    """
    try:
        # Versuche zu initialisieren (funktioniert wenn bereits authentifiziert)
        ee.Initialize()
        return True
    except Exception:
        # Versuche mit Service Account
        import os
        credentials_path = "credentials.json"
        if os.path.exists(credentials_path):
            try:
                import json
                with open(credentials_path, 'r') as f:
                    creds = json.load(f)
                    project_id = creds.get('project_id')
                
                credentials = ee.ServiceAccountCredentials(None, credentials_path)
                if project_id:
                    ee.Initialize(credentials, project=project_id)
                else:
                    ee.Initialize(credentials)
                return True
            except Exception as e:
                print(f"Fehler bei Service Account Initialisierung: {e}")
                return False
        return False


if __name__ == "__main__":
    print("=" * 60)
    print("Wildfire Risk Score Datenabfrage - 10x10m Square")
    print("=" * 60)
    
    # Initialisiere Earth Engine
    print("\n0. Initialisiere Earth Engine...")
    if not initialize_earth_engine():
        print("✗ Fehler bei Initialisierung")
        print("\nBitte führe zuerst earth_engine_setup.py aus!")
        exit(1)
    print("✓ Earth Engine initialisiert")
    
    # Erstelle Test-Square
    print("\n1. Erstelle Test-Square...")
    square = get_test_square()
    print_square_info(square)
    
    # Extrahiere alle Risiko-Daten
    print(f"\n2. Extrahiere alle Wildfire-Risiko-Daten für {TEST_DATE}...")
    try:
        all_data = extract_all_risk_data(square, TEST_DATE, FIRE_HISTORY_START_DATE)
        
        # Zeige Ergebnisse
        print_risk_data(all_data)
        
        # Speichere Daten
        print("\n3. Speichere Daten...")
        save_data_to_json(all_data)
        
        print("\n" + "=" * 60)
        print("✓ Datenabfrage erfolgreich abgeschlossen!")
        print("=" * 60)
        
    except Exception as e:
        print(f"\n✗ Fehler beim Extrahieren der Daten: {e}")
        import traceback
        traceback.print_exc()
        exit(1)

