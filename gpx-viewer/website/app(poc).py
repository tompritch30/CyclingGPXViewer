from flask import Flask, jsonify, render_template, request
from flask_cors import CORS
import os
import json
import logging
import gpxpy
import gpxpy.gpx
import uuid
from datetime import datetime

# --- Setup ---
app = Flask(__name__, template_folder='templates')
CORS(app)

# Folders & files
GPX_FOLDER = "/home/tom/dev/cyclingGPX/gpx-viewer/website/gpx"
JSON_FILE = "/home/tom/dev/cyclingGPX/gpx-viewer/website/metadata.json"
os.makedirs(GPX_FOLDER, exist_ok=True)

# Logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] [%(filename)s:%(lineno)d] %(message)s"
)

# --- Helpers ---
def read_metadata():
    if not os.path.exists(JSON_FILE):
        return {}
    try:
        with open(JSON_FILE, "r") as f:
            return json.load(f)
    except (json.JSONDecodeError, IOError) as e:
        logging.error(f"Failed to read or parse metadata: {e}")
        return {}

def write_metadata(metadata):
    try:
        with open(JSON_FILE, "w") as f:
            json.dump(metadata, f, indent=2)
    except IOError as e:
        logging.error(f"Failed to write metadata: {e}")

def parse_gpx_file(filepath):
    """Parses a GPX file and returns its data structure."""
    try:
        with open(filepath, 'r', encoding='utf-8') as gpx_file:
            gpx = gpxpy.parse(gpx_file)
            tracks = [[[p.latitude, p.longitude] for p in segment.points] for track in gpx.tracks for segment in track.segments]
            waypoints = [[wp.latitude, wp.longitude] for wp in gpx.waypoints]
            return {"tracks": tracks, "waypoints": waypoints}
    except Exception as e:
        logging.error(f"Failed to parse GPX {os.path.basename(filepath)}: {e}")
        return None

def create_gpx_from_waypoints(waypoints_data):
    """Generates GPX XML content from a list of waypoints."""
    gpx = gpxpy.gpx.GPX()
    gpx_track = gpxpy.gpx.GPXTrack()
    gpx.tracks.append(gpx_track)
    gpx_segment = gpxpy.gpx.GPXTrackSegment()
    gpx_track.segments.append(gpx_segment)

    for i, point in enumerate(waypoints_data):
        lat, lon = point[0], point[1]
        # Add to track
        gpx_segment.points.append(gpxpy.gpx.GPXTrackPoint(latitude=lat, longitude=lon))
        # Add as waypoint
        waypoint = gpxpy.gpx.GPXWaypoint(latitude=lat, longitude=lon, name=f"Point {i+1}")
        gpx.waypoints.append(waypoint)
    
    return gpx.to_xml()

# --- API Routes ---
@app.route("/")
@app.route("/route/<path:filename>")
def index(filename=None):
    """Serves the main single-page application."""
    return render_template("index.html")

@app.route("/api/routes", methods=['GET'])
def get_all_routes():
    """Returns a paginated list of all routes."""
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('limit', 20, type=int)
    
    routes = []
    metadata = read_metadata()
    all_files = sorted([f for f in os.listdir(GPX_FOLDER) if f.endswith(".gpx")])

    total_files = len(all_files)
    start_index = (page - 1) * per_page
    end_index = start_index + per_page
    paginated_files = all_files[start_index:end_index]

    for filename in paginated_files:
        filepath = os.path.join(GPX_FOLDER, filename)
        gpx_data = parse_gpx_file(filepath)
        if gpx_data:
            meta = metadata.get(filename, {})
            routes.append({
                "file": filename,
                "name": meta.get("name", os.path.splitext(filename)[0]),
                "marked": meta.get("marked", False),
                "tracks": gpx_data["tracks"] # Only send tracks for overview
            })
            
    return jsonify({
        "routes": routes,
        "total": total_files,
        "page": page,
        "per_page": per_page
    })

@app.route("/api/route/<path:filename>", methods=['GET'])
def get_single_route(filename):
    """Returns the full waypoint data for a single route."""
    filepath = os.path.join(GPX_FOLDER, filename)
    if not os.path.exists(filepath):
        return jsonify({"error": "File not found"}), 404
    
    gpx_data = parse_gpx_file(filepath)
    if gpx_data:
        metadata = read_metadata()
        meta = metadata.get(filename, {})
        return jsonify({
            "file": filename,
            "name": meta.get("name", os.path.splitext(filename)[0]),
            "waypoints": gpx_data["waypoints"]
        })
    return jsonify({"error": "Failed to parse GPX file"}), 500


@app.route("/api/routes", methods=['POST'])
def save_route():
    """Saves a route. If original_file is provided, it's a 'save as' operation."""
    data = request.get_json()
    if not data or 'waypoints' not in data or 'name' not in data:
        return jsonify({"error": "Invalid data provided"}), 400

    original_file = data.get('original_file')
    gpx_xml = create_gpx_from_waypoints(data['waypoints'])
    
    try:
        if original_file:
            base, _ = os.path.splitext(original_file)
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"{base}_{timestamp}.gpx"
        else:
            # It's a brand new route
            slug = data['name'].lower().replace(' ', '_').replace('.', '')
            filename = f"{slug}_{uuid.uuid4().hex[:6]}.gpx"

        filepath = os.path.join(GPX_FOLDER, filename)
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(gpx_xml)
        
        metadata = read_metadata()
        metadata[filename] = {"name": data['name'], "marked": False}
        write_metadata(metadata)

        logging.info(f"Successfully saved route: {filename} with name: {data['name']}")
        return jsonify({"success": True, "file": filename, "name": data['name']}), 201

    except Exception as e:
        logging.error(f"Failed to write GPX file: {e}")
        return jsonify({"error": "Could not save file to server"}), 500

@app.route("/api/mark/<path:filename>", methods=['POST'])
def mark_route(filename):
    """Toggles the 'marked' status of a route."""
    metadata = read_metadata()
    if filename not in metadata:
        metadata[filename] = {"name": os.path.splitext(filename)[0]}
    
    current_status = metadata[filename].get("marked", False)
    metadata[filename]["marked"] = not current_status
    write_metadata(metadata)
    
    logging.info(f"Toggled mark for {filename} to {metadata[filename]['marked']}")
    return jsonify({"success": True, "marked": metadata[filename]["marked"]})

# --- Run App ---
if __name__ == "__main__":
    logging.info("Starting Advanced GPX Editor API...")
    app.run(debug=True, port=4000)
