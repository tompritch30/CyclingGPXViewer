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
            
            # Extract tracks
            tracks = []
            for track in gpx.tracks:
                for segment in track.segments:
                    track_points = [[p.latitude, p.longitude] for p in segment.points]
                    if track_points:
                        tracks.append(track_points)
            
            # Extract waypoints with names
            waypoints = []
            for wp in gpx.waypoints:
                waypoint_name = wp.name or f"Waypoint {len(waypoints) + 1}"
                waypoints.append([wp.latitude, wp.longitude, waypoint_name])
            
            # If no waypoints but we have tracks, create waypoints from track points
            if not waypoints and tracks:
                for i, track in enumerate(tracks):
                    if track:
                        # Use first, middle, and last points as waypoints
                        waypoints.append([track[0][0], track[0][1], f"Start {i+1}"])
                        if len(track) > 2:
                            mid_idx = len(track) // 2
                            waypoints.append([track[mid_idx][0], track[mid_idx][1], f"Mid {i+1}"])
                        if len(track) > 1:
                            waypoints.append([track[-1][0], track[-1][1], f"End {i+1}"])
            
            return {"tracks": tracks, "waypoints": waypoints}
    except Exception as e:
        logging.error(f"Failed to parse GPX {os.path.basename(filepath)}: {e}")
        return None

def create_gpx_from_waypoints(waypoints_data, route_name="Route"):
    """Generates GPX XML content from a list of waypoints."""
    gpx = gpxpy.gpx.GPX()
    
    # Set GPX metadata
    gpx.name = route_name
    gpx.description = f"Route created with GPX Route Editor - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
    
    # Create track from waypoints
    gpx_track = gpxpy.gpx.GPXTrack()
    gpx_track.name = route_name
    gpx.tracks.append(gpx_track)
    
    gpx_segment = gpxpy.gpx.GPXTrackSegment()
    gpx_track.segments.append(gpx_segment)
    
    # Add waypoints and track points
    for i, point in enumerate(waypoints_data):
        lat, lon = point[0], point[1]
        name = point[2] if len(point) > 2 else f"Waypoint {i+1}"
        
        # Add to track
        gpx_segment.points.append(gpxpy.gpx.GPXTrackPoint(latitude=lat, longitude=lon))
        
        # Add as waypoint
        waypoint = gpxpy.gpx.GPXWaypoint(latitude=lat, longitude=lon, name=name)
        gpx.waypoints.append(waypoint)
    
    return gpx.to_xml()

def calculate_route_stats(waypoints):
    """Calculate basic route statistics."""
    if len(waypoints) < 2:
        return {"distance": 0, "waypoint_count": len(waypoints)}
    
    # Simple distance calculation using Haversine formula
    import math
    
    def haversine_distance(lat1, lon1, lat2, lon2):
        R = 6371000  # Earth's radius in meters
        
        lat1_rad = math.radians(lat1)
        lat2_rad = math.radians(lat2)
        delta_lat = math.radians(lat2 - lat1)
        delta_lon = math.radians(lon2 - lon1)
        
        a = math.sin(delta_lat/2)**2 + math.cos(lat1_rad) * math.cos(lat2_rad) * math.sin(delta_lon/2)**2
        c = 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))
        
        return R * c
    
    total_distance = 0
    for i in range(len(waypoints) - 1):
        lat1, lon1 = waypoints[i][0], waypoints[i][1]
        lat2, lon2 = waypoints[i+1][0], waypoints[i+1][1]
        total_distance += haversine_distance(lat1, lon1, lat2, lon2)
    
    return {
        "distance": round(total_distance / 1000, 2),  # Convert to km
        "waypoint_count": len(waypoints)
    }

# --- API Routes ---
@app.route("/")
@app.route("/route/<path:filename>")
def index(filename=None):
    """Serves the main single-page application."""
    return render_template("index.html")

@app.route("/api/routes", methods=['GET'])
def get_all_routes():
    """Returns a list of all routes with basic info for overview."""
    try:
        routes = []
        metadata = read_metadata()
        
        if not os.path.exists(GPX_FOLDER) or not os.listdir(GPX_FOLDER):
            return jsonify({"routes": [], "total": 0})
        
        for filename in sorted(os.listdir(GPX_FOLDER)):
            if filename.endswith(".gpx"):
                filepath = os.path.join(GPX_FOLDER, filename)
                gpx_data = parse_gpx_file(filepath)
                if gpx_data:
                    meta = metadata.get(filename, {})
                    stats = calculate_route_stats(gpx_data["waypoints"])
                    
                    routes.append({
                        "file": filename,
                        "name": meta.get("name", os.path.splitext(filename)[0]),
                        "marked": meta.get("marked", False),
                        "tracks": gpx_data["tracks"],
                        "waypoints": gpx_data["waypoints"],
                        "stats": stats
                    })
        
        logging.info(f"Loaded {len(routes)} routes")
        return jsonify({"routes": routes, "total": len(routes)})
        
    except Exception as e:
        logging.error(f"Error loading routes: {e}")
        return jsonify({"error": "Failed to load routes", "routes": [], "total": 0}), 500

@app.route("/api/route/<path:filename>", methods=['GET'])
def get_single_route(filename):
    """Returns the full data for a single route."""
    try:
        filepath = os.path.join(GPX_FOLDER, filename)
        if not os.path.exists(filepath):
            return jsonify({"error": "File not found"}), 404
        
        gpx_data = parse_gpx_file(filepath)
        if not gpx_data:
            return jsonify({"error": "Failed to parse GPX file"}), 500
        
        metadata = read_metadata()
        meta = metadata.get(filename, {})
        stats = calculate_route_stats(gpx_data["waypoints"])
        
        return jsonify({
            "file": filename,
            "name": meta.get("name", os.path.splitext(filename)[0]),
            "marked": meta.get("marked", False),
            "tracks": gpx_data["tracks"],
            "waypoints": gpx_data["waypoints"],
            "stats": stats
        })
        
    except Exception as e:
        logging.error(f"Error loading route {filename}: {e}")
        return jsonify({"error": "Failed to load route"}), 500

@app.route("/api/routes", methods=['POST'])
def create_route():
    """Creates a new route."""
    try:
        data = request.get_json()
        if not data or 'waypoints' not in data or 'name' not in data:
            return jsonify({"error": "Invalid data provided - missing waypoints or name"}), 400
        
        if len(data['waypoints']) < 2:
            return jsonify({"error": "Route must have at least 2 waypoints"}), 400
        
        route_name = data['name'].strip()
        if not route_name:
            return jsonify({"error": "Route name cannot be empty"}), 400
        
        # Generate filename
        safe_name = "".join(c for c in route_name if c.isalnum() or c in (' ', '-', '_')).rstrip()
        safe_name = safe_name.replace(' ', '_').lower()
        filename = f"{safe_name}_{uuid.uuid4().hex[:8]}.gpx"
        
        # Create GPX content
        gpx_xml = create_gpx_from_waypoints(data['waypoints'], route_name)
        
        # Save file
        filepath = os.path.join(GPX_FOLDER, filename)
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(gpx_xml)
        
        # Update metadata
        metadata = read_metadata()
        metadata[filename] = {
            "name": route_name,
            "marked": False,
            "created": datetime.now().isoformat(),
            "type": data.get("type", "cycling")
        }
        write_metadata(metadata)
        
        logging.info(f"Successfully created route: {filename} with name: {route_name}")
        
        # Return the created route data
        gpx_data = parse_gpx_file(filepath)
        stats = calculate_route_stats(gpx_data["waypoints"])
        
        return jsonify({
            "success": True,
            "file": filename,
            "name": route_name,
            "tracks": gpx_data["tracks"],
            "waypoints": gpx_data["waypoints"],
            "stats": stats
        }), 201
        
    except Exception as e:
        logging.error(f"Failed to create route: {e}")
        return jsonify({"error": "Could not save route to server"}), 500

@app.route("/api/route/<path:filename>", methods=['PUT'])
def update_route(filename):
    """Updates an existing route."""
    try:
        filepath = os.path.join(GPX_FOLDER, filename)
        if not os.path.exists(filepath):
            return jsonify({"error": "File not found"}), 404
        
        data = request.get_json()
        if not data or 'waypoints' not in data:
            return jsonify({"error": "Invalid data - missing waypoints"}), 400
        
        if len(data['waypoints']) < 2:
            return jsonify({"error": "Route must have at least 2 waypoints"}), 400
        
        # Get current metadata
        metadata = read_metadata()
        current_meta = metadata.get(filename, {})
        route_name = data.get('name', current_meta.get('name', os.path.splitext(filename)[0]))
        
        # Create updated GPX content
        gpx_xml = create_gpx_from_waypoints(data['waypoints'], route_name)
        
        # Save updated file
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(gpx_xml)
        
        # Update metadata
        current_meta.update({
            "name": route_name,
            "modified": datetime.now().isoformat()
        })
        metadata[filename] = current_meta
        write_metadata(metadata)
        
        logging.info(f"Successfully updated route: {filename}")
        
        # Return updated route data
        gpx_data = parse_gpx_file(filepath)
        stats = calculate_route_stats(gpx_data["waypoints"])
        
        return jsonify({
            "success": True,
            "file": filename,
            "name": route_name,
            "tracks": gpx_data["tracks"],
            "waypoints": gpx_data["waypoints"],
            "stats": stats
        })
        
    except Exception as e:
        logging.error(f"Failed to update route {filename}: {e}")
        return jsonify({"error": "Failed to update route"}), 500

@app.route("/api/route/<path:filename>", methods=['DELETE'])
def delete_route(filename):
    """Deletes a route."""
    try:
        filepath = os.path.join(GPX_FOLDER, filename)
        if not os.path.exists(filepath):
            return jsonify({"error": "File not found"}), 404
        
        # Remove file
        os.remove(filepath)
        
        # Remove from metadata
        metadata = read_metadata()
        if filename in metadata:
            del metadata[filename]
            write_metadata(metadata)
        
        logging.info(f"Successfully deleted route: {filename}")
        return jsonify({"success": True, "message": f"Route {filename} deleted"})
        
    except Exception as e:
        logging.error(f"Failed to delete route {filename}: {e}")
        return jsonify({"error": "Failed to delete route"}), 500

@app.route("/api/route/<path:filename>/mark", methods=['POST'])
def toggle_mark_route(filename):
    """Toggles the 'marked' status of a route."""
    try:
        filepath = os.path.join(GPX_FOLDER, filename)
        if not os.path.exists(filepath):
            return jsonify({"error": "File not found"}), 404
        
        metadata = read_metadata()
        if filename not in metadata:
            metadata[filename] = {"name": os.path.splitext(filename)[0]}
        
        current_status = metadata[filename].get("marked", False)
        metadata[filename]["marked"] = not current_status
        write_metadata(metadata)
        
        logging.info(f"Toggled mark for {filename} to {metadata[filename]['marked']}")
        return jsonify({
            "success": True, 
            "marked": metadata[filename]["marked"],
            "file": filename
        })
        
    except Exception as e:
        logging.error(f"Failed to toggle mark for {filename}: {e}")
        return jsonify({"error": "Failed to update route"}), 500

@app.route("/api/health", methods=['GET'])
def health_check():
    """Health check endpoint."""
    return jsonify({
        "status": "healthy",
        "gpx_folder_exists": os.path.exists(GPX_FOLDER),
        "routes_count": len([f for f in os.listdir(GPX_FOLDER) if f.endswith('.gpx')]) if os.path.exists(GPX_FOLDER) else 0
    })

# --- Error Handlers ---
@app.errorhandler(404)
def not_found(error):
    return jsonify({"error": "Endpoint not found"}), 404

@app.errorhandler(500)
def internal_error(error):
    return jsonify({"error": "Internal server error"}), 500

# --- Run App ---
if __name__ == "__main__":
    logging.info("Starting Advanced GPX Editor API...")
    logging.info(f"GPX folder: {GPX_FOLDER}")
    logging.info(f"Metadata file: {JSON_FILE}")
    app.run(debug=True, port=4000, host='0.0.0.0')