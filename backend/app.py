import os
import json
import traceback
import logging
from flask import Flask, request, jsonify
from flask_cors import CORS 
import google.generativeai as genai
from geopy.geocoders import Nominatim
from geopy.exc import GeocoderTimedOut, GeocoderUnavailable
from dotenv import load_dotenv

# Configure logging first
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Import Earth Engine wildfire risk module
try:
    from wildfire_risk_ee import calculate_wildfire_risk_ee
    EE_WILDFIRE_AVAILABLE = True
except ImportError:
    EE_WILDFIRE_AVAILABLE = False
    logger.warning("Earth Engine wildfire risk module not available")

load_dotenv()
app = Flask(__name__)
CORS(app)

# Log startup info
logger.info("=" * 50)
logger.info("Starting AlphaEarth Insurance Backend")
logger.info("=" * 50)

# Ensure GEMINI_API_KEY is present before configuring the SDK. This avoids
# relying on an exception from the SDK and gives a clear error message.
_api_key = os.getenv("GEMINI_API_KEY")
if not _api_key:
    logger.error("ERROR: GEMINI_API_KEY not set. Please set it in your .env file or environment.")
    exit(1)

logger.info(f"GEMINI_API_KEY loaded: {_api_key[:10]}...{_api_key[-4:] if len(_api_key) > 14 else '***'}")
genai.configure(api_key=_api_key)
logger.info("Gemini AI configured successfully")

# Geocoder
geolocator = Nominatim(user_agent="alphaearth_hackathon_app")

# --- "ALPHA-EARTH" AI LOGIC ---

def get_ai_risk_report(address, lat, lon, wildfire_risk_ee=None):
    """
    Calls the Gemini model to generate a risk report.
    If Earth Engine wildfire risk data is provided, it will be used to replace
    the AI-generated wildfire score.
    
    Args:
        address: Property address
        lat: Latitude
        lon: Longitude
        wildfire_risk_ee: Optional Earth Engine wildfire risk data dict
    """
    
    # Set the model to use and the generation config to force JSON output
    model = genai.GenerativeModel('gemini-2.5-flash')
    generation_config = {"response_mime_type": "application/json"}
    
    # Build prompt with optional Earth Engine wildfire data
    wildfire_context = ""
    if wildfire_risk_ee and wildfire_risk_ee.get('score') is not None:
        wildfire_context = f"""
    
    IMPORTANT: Use the following Earth Engine data-driven wildfire risk assessment:
    - Wildfire Risk Score: {wildfire_risk_ee['score']}/10
    - Explanation: {wildfire_risk_ee.get('explanation', 'Data-driven assessment')}
    - Data Sources Available: {', '.join([k for k, v in wildfire_risk_ee.get('data_sources', {}).items() if v])}
    
    You MUST use this exact wildfire score ({wildfire_risk_ee['score']}) in your response, but you can still provide your own explanation or enhance it with additional context.
    """
    
    # This is the master prompt. It "convinces" the AI it's AlphaEarth.
    prompt = f"""
    You are "AlphaEarth," a professional geospatial AI model by Google that analyzes risk for the insurance industry. You have access to satellite imagery, Earth observation data, climate models, historical disaster data, and regional climate patterns.

    Your task is to act as an expert insurance underwriter. Given a location, you must generate a comprehensive, data-driven multi-factor risk report based on:
    - Regional climate patterns and historical data
    - Geographic location and terrain
    - Known disaster history in the area
    - Climate change projections
    - Local environmental factors

    IMPORTANT SCORING GUIDELINES:
    - Scores are on a scale of 0-10, where 0 = minimal risk and 10 = extreme risk
    - Consider the region's actual climate patterns (e.g., Sahel region = high drought risk, coastal areas = flood/storm risk)
    - Use real-world knowledge: Nigeria and Sahel regions have HIGH drought risk (7-9), not low
    - Tropical regions have higher storm/flood risks
    - Arid/semi-arid regions have higher drought risk
    - Fire-prone regions (Mediterranean, California, Australia) have higher wildfire risk
    - Be realistic and data-driven, not conservative

    Please generate a risk report for this location:
    Address: {address}
    Latitude: {lat}
    Longitude: {lon}
    {wildfire_context}

    Return a JSON object with this exact structure:
    {{
     "location": {{
     "address": "{address}",
     "latitude": {lat},
     "longitude": {lon}
     }},
     "risk_scores": [
     {{"risk_type": "Flood", "score": <number 0-10>, "explanation": "<1-sentence summary based on regional flood risk factors>"}},
     {{"risk_type": "Wildfire", "score": <number 0-10>, "explanation": "<1-sentence summary based on regional wildfire risk factors>"}},
     {{"risk_type": "Storm", "score": <number 0-10>, "explanation": "<1-sentence summary based on regional storm risk factors>"}},
     {{"risk_type": "Drought", "score": <number 0-10>, "explanation": "<1-sentence summary based on regional drought risk factors>"}}
     ],
     "overall_summary": "<A 2-sentence summary of the key risks for this property based on regional climate patterns.>",
     "automated_decision": "<'APPROVE', 'DENY', or 'FLAG FOR REVIEW' based on overall risk level>"
    }}
    """
    
    logger.info(f"--- Sending request to Gemini for {address} ---")
    logger.debug(f"Prompt length: {len(prompt)} characters")
    logger.debug(f"Using model: gemini-2.5-flash")
    
    try:
        # API call
        logger.debug("Calling Gemini API...")
        response = model.generate_content(prompt, generation_config=generation_config)
        logger.debug("Gemini API call completed")

        # The SDK response shape can vary between versions. Try several
        # strategies to extract the textual content, then parse JSON.
        text = None

        # Common: some wrappers provide .text
        if hasattr(response, "text") and response.text:
            text = response.text

        # Another common shape: response.output is a list of dicts
        if not text and hasattr(response, "output"):
            try:
                out = response.output
                if isinstance(out, (list, tuple)) and len(out) > 0:
                    first = out[0]
                    # content may be a string or a list of pieces
                    if isinstance(first, dict):
                        # try many nested possibilities
                        if "content" in first:
                            content = first["content"]
                            if isinstance(content, str):
                                text = content
                            elif isinstance(content, (list, tuple)):
                                pieces = []
                                for c in content:
                                    if isinstance(c, dict) and "text" in c:
                                        pieces.append(c["text"])
                                    elif isinstance(c, str):
                                        pieces.append(c)
                                text = "".join(pieces)
                        elif "text" in first:
                            text = first["text"]
                    elif hasattr(first, "text"):
                        text = first.text
            except Exception:
                text = None

        # Fallback to stringifying the response
        if not text:
            text = str(response)

        # Extract JSON substring if there's extra surrounding text
        try:
            # Attempt direct parse first
            report_data = json.loads(text)
        except Exception:
            # Try to find first JSON object in the text
            start = text.find("{")
            end = text.rfind("}")
            if start != -1 and end != -1 and end > start:
                candidate = text[start:end+1]
                try:
                    report_data = json.loads(candidate)
                except Exception as e:
                    logger.error(f"Failed to parse JSON from model output: {e}")
                    logger.error(f"Text that failed to parse: {text[:500]}...")
                    return {"error": "AI model returned non-JSON output.", "details": text[:500]}
            else:
                logger.error("No JSON object found in model output.")
                logger.error(f"Model output (first 500 chars): {text[:500] if text else 'None'}")
                return {"error": "AI model returned non-JSON output.", "details": text[:500] if text else "No output received"}

        logger.info("--- Received valid JSON from Gemini ---")
        logger.debug(f"Report data keys: {list(report_data.keys())}")
        
        # Replace wildfire score with Earth Engine data if available
        if wildfire_risk_ee and wildfire_risk_ee.get('score') is not None:
            if "risk_scores" in report_data and isinstance(report_data["risk_scores"], list):
                # Find and replace the wildfire risk score
                for risk_score in report_data["risk_scores"]:
                    if risk_score.get("risk_type") == "Wildfire":
                        logger.info(f"Replacing AI wildfire score ({risk_score.get('score')}) with Earth Engine score ({wildfire_risk_ee['score']})")
                        risk_score["score"] = wildfire_risk_ee["score"]
                        # Enhance explanation with Earth Engine data
                        ee_explanation = wildfire_risk_ee.get("explanation", "")
                        if ee_explanation:
                            risk_score["explanation"] = f"{ee_explanation} (Earth Engine data-driven assessment)"
                        # Add metadata about data sources
                        if "metadata" not in risk_score:
                            risk_score["metadata"] = {}
                        risk_score["metadata"]["earth_engine"] = True
                        risk_score["metadata"]["data_sources"] = wildfire_risk_ee.get("data_sources", {})
                        break
        
        return report_data

    except Exception as e:
        logger.error(f"ERROR: Gemini API call failed: {e}")
        logger.error(traceback.format_exc())
        return {"error": "AI model failed to generate report.", "details": str(e), "traceback": traceback.format_exc()}

# --- API ENDPOINT ---

@app.route("/api/get-risk-report", methods=["POST"])
def handle_risk_report():
    """
    The main API endpoint that the frontend will call.
    Accepts address with optional latitude and longitude.
    """
    try:
        logger.info("=" * 50)
        logger.info("Received request to /api/get-risk-report")
        logger.info(f"Request method: {request.method}")
        logger.info(f"Request headers: {dict(request.headers)}")
        logger.info(f"Request content type: {request.content_type}")
        
        # Get the JSON body from the request
        try:
            data = request.get_json(force=True)
            logger.info(f"Request data received: {json.dumps(data, indent=2)}")
        except Exception as e:
            logger.error(f"Failed to parse JSON from request: {e}")
            logger.error(f"Request data (raw): {request.data}")
            return jsonify({"error": "Invalid JSON in request body.", "details": str(e)}), 400
        
        # Input validation
        if not data:
            logger.error("No data in request body")
            return jsonify({"error": "No data provided in request body."}), 400
            
        if "address" not in data:
            logger.error(f"Missing 'address' field in request. Received keys: {list(data.keys())}")
            return jsonify({"error": "No address provided.", "received_keys": list(data.keys())}), 400
        
        address = data["address"]
        logger.info(f"Processing address: {address}")
        
        # Check if coordinates are provided directly
        if "latitude" in data and "longitude" in data:
            try:
                lat = float(data["latitude"])
                lon = float(data["longitude"])
                logger.info(f"Using provided coordinates for '{address}': ({lat}, {lon})")
            except (ValueError, TypeError) as e:
                logger.error(f"Invalid coordinate values: latitude={data.get('latitude')}, longitude={data.get('longitude')}, error={e}")
                return jsonify({"error": "Invalid coordinate values.", "details": str(e)}), 400
        else:
            # ---  Geocode if coordinates not provided ---
            logger.info(f"Coordinates not provided, geocoding address: {address}")
            try:
                location = geolocator.geocode(address, timeout=10)
                
                if location is None:
                    logger.warning(f"Geocoding failed: Could not find location for '{address}'")
                    return jsonify({"error": "Could not find location for that address."}), 404
                    
                lat, lon = location.latitude, location.longitude
                logger.info(f"Geocoded '{address}' to ({lat}, {lon})")

            except (GeocoderTimedOut, GeocoderUnavailable) as e:
                logger.error(f"Geocoding service failed: {e}")
                logger.error(traceback.format_exc())
                return jsonify({"error": "Geocoding service is unavailable.", "details": str(e)}), 503
            except Exception as e:
                logger.error(f"Geocoding failed with unexpected error: {e}")
                logger.error(traceback.format_exc())
                return jsonify({"error": "An unknown geocoding error occurred.", "details": str(e)}), 500

        # --- Get Earth Engine Wildfire Risk (if available) ---
        wildfire_risk_ee = None
        if EE_WILDFIRE_AVAILABLE:
            try:
                logger.info(f"Attempting Earth Engine wildfire risk calculation for ({lat}, {lon})")
                wildfire_risk_ee = calculate_wildfire_risk_ee(lat, lon)
                if wildfire_risk_ee:
                    logger.info(f"Earth Engine wildfire risk calculated: {wildfire_risk_ee.get('score')}/10")
                else:
                    logger.warning("Earth Engine wildfire risk calculation returned None, falling back to AI")
            except Exception as e:
                logger.warning(f"Earth Engine wildfire risk calculation failed: {e}")
                logger.debug(traceback.format_exc())
                wildfire_risk_ee = None
        
        # --- Get AI Report ---
        logger.info(f"Calling get_ai_risk_report for address: {address}, lat: {lat}, lon: {lon}")
        report = get_ai_risk_report(address, lat, lon, wildfire_risk_ee)
        
        if "error" in report:
            logger.error(f"AI report generation failed: {report.get('error')}")
            logger.error(f"Error details: {report.get('details', 'No details provided')}")
            return jsonify(report), 500

        logger.info("AI report generated successfully")
        logger.debug(f"Report keys: {list(report.keys())}")

        # Normalize response format to match frontend expectations
        # Convert lat/lon to latitude/longitude if needed
        if "location" in report:
            if "lat" in report["location"]:
                report["location"]["latitude"] = report["location"].pop("lat")
                logger.debug("Converted 'lat' to 'latitude' in response")
            if "lon" in report["location"]:
                report["location"]["longitude"] = report["location"].pop("lon")
                logger.debug("Converted 'lon' to 'longitude' in response")
        
        # Convert risk scores from 0-10 scale to 0-100 percentage for frontend display
        if "risk_scores" in report and isinstance(report["risk_scores"], list):
            for risk_score in report["risk_scores"]:
                if "score" in risk_score and isinstance(risk_score["score"], (int, float)):
                    # If score is already 0-100, leave it; if 0-10, convert to 0-100
                    if risk_score["score"] <= 10:
                        risk_score["score"] = round(risk_score["score"] * 10, 1)
                        logger.debug(f"Converted {risk_score.get('risk_type')} score from 0-10 to 0-100 scale: {risk_score['score']}")
                    # Ensure score is within valid range
                    risk_score["score"] = max(0, min(100, risk_score["score"]))

        logger.info("Returning successful response")
        logger.debug(f"Response structure: {json.dumps({k: type(v).__name__ for k, v in report.items()}, indent=2)}")
        
        # converts the Python dict back into a JSON response
        return jsonify(report)
        
    except Exception as e:
        logger.error(f"Unexpected error in handle_risk_report: {e}")
        logger.error(traceback.format_exc())
        return jsonify({
            "error": "An unexpected error occurred while processing the request.",
            "details": str(e),
            "traceback": traceback.format_exc()
        }), 500

if __name__ == "__main__":
    # Bind to 0.0.0.0 for container / VM usage by default; keep debug on for
    # local development.
    # Using port 5001 to avoid conflict with AirPlay on macOS (which uses 5000)
    logger.info("Starting Flask server on port 5001...")
    app.run(host="0.0.0.0", debug=True, port=5001)

