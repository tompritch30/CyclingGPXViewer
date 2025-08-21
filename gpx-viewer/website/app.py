from flask import Flask, jsonify, render_template, request
from flask_cors import CORS
import os
import json
import logging
import uuid
from datetime import datetime
from services.gpx_service import GPXService
from services.route_service import RouteService
from services.geocoding_service import GeocodingService

# Setup
app = Flask(__name__, template_folder='templates', static_folder='static')
CORS(app)

# Configuration
app.config.update({
    'GPX_FOLDER': os.environ.get('GPX_FOLDER', '/home/tom/dev/cyclingGPX/gpx-viewer/website/gpx'), # './data/gpx'),
    'METADATA_FILE': os.environ.get('METADATA_FILE', '/home/tom/dev/cyclingGPX/gpx-viewer/website/metadata.json'), #'./data/metadata.json'),
    'MAX_FILE_SIZE': 50 * 1024 * 1024,  # 50MB
})

# Ensure data directories exist
os.makedirs(app.config['GPX_FOLDER'], exist_ok=True)
os.makedirs(os.path.dirname(app.config['METADATA_FILE']), exist_ok=True)

# Initialize services
gpx_service = GPXService(app.config['GPX_FOLDER'])
route_service = RouteService(app.config['METADATA_FILE'], gpx_service)
geocoding_service = GeocodingService()

# Logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] [%(filename)s:%(lineno)d] %(message)s"
)

# Routes
@app.route("/")
def index():
    """Serves the main application."""
    logging.info(app.config['GPX_FOLDER'])
    logging.info(app.config['METADATA_FILE'])
    return render_template("index.html")

@app.route("/api/routes", methods=['GET'])
def get_routes():
    """Get all routes with optional bounds filtering."""
    try:
        bounds = None
        if all(param in request.args for param in ['north', 'south', 'east', 'west']):
            bounds = {
                'north': float(request.args['north']),
                'south': float(request.args['south']),
                'east': float(request.args['east']),
                'west': float(request.args['west'])
            }
        
        routes = route_service.get_routes(bounds=bounds)
        return jsonify({"routes": routes, "total": len(routes)})
    except Exception as e:
        logging.error(f"Error getting routes: {e}")
        return jsonify({"error": "Failed to load routes"}), 500

@app.route("/api/route/<filename>", methods=['GET'])
def get_route(filename):
    """Get a specific route."""
    try:
        route = route_service.get_route(filename)
        if not route:
            return jsonify({"error": "Route not found"}), 404
        return jsonify(route)
    except Exception as e:
        logging.error(f"Error getting route {filename}: {e}")
        return jsonify({"error": "Failed to load route"}), 500

@app.route("/api/routes", methods=['POST'])
def create_route():
    """Create a new route."""
    try:
        data = request.get_json()
        if not data or not data.get('waypoints') or not data.get('name'):
            return jsonify({"error": "Missing required data"}), 400
        
        route = route_service.create_route(
            name=data['name'],
            waypoints=data['waypoints'],
            route_type=data.get('type', 'cycling'),
            description=data.get('description', '')
        )
        
        return jsonify(route), 201
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    except Exception as e:
        logging.error(f"Error creating route: {e}")
        return jsonify({"error": "Failed to create route"}), 500

@app.route("/api/route/<filename>", methods=['PUT'])
def update_route(filename):
    """Update an existing route."""
    try:
        data = request.get_json()
        if not data or not data.get('waypoints'):
            return jsonify({"error": "Missing waypoints data"}), 400
        
        # Create versioned backup
        original_route = route_service.get_route(filename)
        if original_route:
            route_service.create_version_backup(filename, original_route)
        
        route = route_service.update_route(
            filename=filename,
            waypoints=data['waypoints'],
            name=data.get('name'),
            description=data.get('description')
        )
        
        if not route:
            return jsonify({"error": "Route not found"}), 404
        
        return jsonify(route)
    except Exception as e:
        logging.error(f"Error updating route {filename}: {e}")
        return jsonify({"error": "Failed to update route"}), 500

@app.route("/api/route/<filename>", methods=['DELETE'])
def delete_route(filename):
    """Delete a route."""
    try:
        success = route_service.delete_route(filename)
        if not success:
            return jsonify({"error": "Route not found"}), 404
        
        return jsonify({"message": "Route deleted successfully"})
    except Exception as e:
        logging.error(f"Error deleting route {filename}: {e}")
        return jsonify({"error": "Failed to delete route"}), 500

@app.route("/api/route/<filename>/favorite", methods=['POST'])
def toggle_favorite(filename):
    """Toggle route favorite status."""
    try:
        result = route_service.toggle_favorite(filename)
        if not result:
            return jsonify({"error": "Route not found"}), 404
        
        return jsonify(result)
    except Exception as e:
        logging.error(f"Error toggling favorite for {filename}: {e}")
        return jsonify({"error": "Failed to update route"}), 500

@app.route("/api/geocode", methods=['GET'])
def geocode():
    """Geocode an address to coordinates."""
    try:
        query = request.args.get('q', '').strip()
        if not query:
            return jsonify({"error": "No search query provided"}), 400
        
        results = geocoding_service.geocode(query)
        return jsonify({"results": results})
    except Exception as e:
        logging.error(f"Error geocoding '{query}': {e}")
        return jsonify({"error": "Geocoding failed"}), 500

@app.route("/api/route/<filename>/versions", methods=['GET'])
def get_route_versions(filename):
    """Get all versions of a route."""
    try:
        versions = route_service.get_route_versions(filename)
        return jsonify({"versions": versions})
    except Exception as e:
        logging.error(f"Error getting versions for {filename}: {e}")
        return jsonify({"error": "Failed to load versions"}), 500

@app.route("/api/health", methods=['GET'])
def health_check():
    """Health check endpoint."""
    try:
        gpx_folder_exists = os.path.exists(app.config['GPX_FOLDER'])
        route_count = len([f for f in os.listdir(app.config['GPX_FOLDER']) 
                          if f.endswith('.gpx')]) if gpx_folder_exists else 0
        
        return jsonify({
            "status": "healthy",
            "gpx_folder_exists": gpx_folder_exists,
            "routes_count": route_count,
            "version": "2.0"
        })
    except Exception as e:
        return jsonify({"status": "unhealthy", "error": str(e)}), 500

# Error handlers
@app.errorhandler(404)
def not_found(error):
    return jsonify({"error": "Endpoint not found"}), 404

@app.errorhandler(500)
def internal_error(error):
    return jsonify({"error": "Internal server error"}), 500

if __name__ == "__main__":
    logging.info("Starting GPX Route Editor API v2.0...")
    logging.info(f"GPX folder: {app.config['GPX_FOLDER']}")
    logging.info(f"Metadata file: {app.config['METADATA_FILE']}")
    app.run(debug=True, port=4000, host='0.0.0.0')