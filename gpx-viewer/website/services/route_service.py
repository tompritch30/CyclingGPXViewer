import os
import json
import logging
import uuid
import shutil
from datetime import datetime
from typing import List, Dict, Optional
from .gpx_service import GPXService

class RouteService:
    """Service for route management and metadata operations."""
    
    def __init__(self, metadata_file: str, gpx_service: GPXService):
        self.metadata_file = metadata_file
        self.gpx_service = gpx_service
        
    def _read_metadata(self) -> Dict:
        """Read metadata from JSON file."""
        if not os.path.exists(self.metadata_file):
            return {}
        try:
            with open(self.metadata_file, 'r') as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError) as e:
            logging.error(f"Failed to read metadata: {e}")
            return {}
    
    def _write_metadata(self, metadata: Dict) -> None:
        """Write metadata to JSON file."""
        try:
            os.makedirs(os.path.dirname(self.metadata_file), exist_ok=True)
            with open(self.metadata_file, 'w') as f:
                json.dump(metadata, f, indent=2)
        except IOError as e:
            logging.error(f"Failed to write metadata: {e}")
            raise
    
    def get_routes(self, bounds: Optional[Dict] = None) -> List[Dict]:
        """Get all routes, optionally filtered by map bounds."""
        routes = []
        metadata = self._read_metadata()
        
        gpx_files = [f for f in os.listdir(self.gpx_service.gpx_folder) 
                    if f.endswith('.gpx') and not f.startswith('.')]
        
        for filename in sorted(gpx_files):
            filepath = os.path.join(self.gpx_service.gpx_folder, filename)
            gpx_data = self.gpx_service.parse_gpx_file(filepath)
            
            if not gpx_data:
                continue
            
            meta = metadata.get(filename, {})
            stats = self.gpx_service.calculate_route_stats(gpx_data["waypoints"])
            
            # Filter by bounds if provided
            if bounds and stats.get('bounds'):
                if not self.gpx_service.get_route_bounds_overlap(stats['bounds'], bounds):
                    continue
            
            route = {
                "filename": filename,
                "name": meta.get("name", os.path.splitext(filename)[0]),
                "description": meta.get("description", ""),
                "is_favorite": meta.get("is_favorite", False),
                "created_at": meta.get("created_at"),
                "modified_at": meta.get("modified_at"),
                "route_type": meta.get("route_type", "cycling"),
                "tracks": gpx_data["tracks"],
                "waypoints": gpx_data["waypoints"],
                "stats": stats,
                "version_count": len(self.get_route_versions(filename))
            }
            
            routes.append(route)
        
        # Sort: favorites first, then by modified date
        routes.sort(key=lambda r: (not r['is_favorite'], 
                                 r.get('modified_at', ''), 
                                 r['name']))
        
        return routes
    
    def get_route(self, filename: str) -> Optional[Dict]:
        """Get a specific route by filename."""
        filepath = os.path.join(self.gpx_service.gpx_folder, filename)
        if not os.path.exists(filepath):
            return None
        
        gpx_data = self.gpx_service.parse_gpx_file(filepath)
        if not gpx_data:
            return None
        
        metadata = self._read_metadata()
        meta = metadata.get(filename, {})
        stats = self.gpx_service.calculate_route_stats(gpx_data["waypoints"])
        
        return {
            "filename": filename,
            "name": meta.get("name", os.path.splitext(filename)[0]),
            "description": meta.get("description", ""),
            "is_favorite": meta.get("is_favorite", False),
            "created_at": meta.get("created_at"),
            "modified_at": meta.get("modified_at"),
            "route_type": meta.get("route_type", "cycling"),
            "tracks": gpx_data["tracks"],
            "waypoints": gpx_data["waypoints"],
            "stats": stats,
            "versions": self.get_route_versions(filename)
        }
    
    def create_route(self, name: str, waypoints: List, route_type: str = "cycling", 
                    description: str = "") -> Dict:
        """Create a new route."""
        if len(waypoints) < 2:
            raise ValueError("Route must have at least 2 waypoints")
        
        if not name.strip():
            raise ValueError("Route name cannot be empty")
        
        # Generate filename
        safe_name = "".join(c for c in name.strip() if c.isalnum() or c in (' ', '-', '_'))
        safe_name = safe_name.replace(' ', '_').lower()[:30]  # Limit length
        filename = f"{safe_name}_{uuid.uuid4().hex[:8]}.gpx"
        
        # Create GPX content
        gpx_content = self.gpx_service.create_gpx_from_waypoints(
            waypoints, name, description
        )
        
        # Save file
        self.gpx_service.save_gpx_file(filename, gpx_content)
        
        # Update metadata
        metadata = self._read_metadata()
        now = datetime.now().isoformat()
        metadata[filename] = {
            "name": name,
            "description": description,
            "route_type": route_type,
            "is_favorite": False,
            "created_at": now,
            "modified_at": now,
            "created_by": "GPX Route Editor"
        }
        self._write_metadata(metadata)
        
        logging.info(f"Created route: {filename} - {name}")
        
        # Return the created route
        return self.get_route(filename)
    
    def update_route(self, filename: str, waypoints: List, name: Optional[str] = None, 
                    description: Optional[str] = None) -> Optional[Dict]:
        """Update an existing route."""
        if not os.path.exists(os.path.join(self.gpx_service.gpx_folder, filename)):
            return None
        
        if len(waypoints) < 2:
            raise ValueError("Route must have at least 2 waypoints")
        
        metadata = self._read_metadata()
        meta = metadata.get(filename, {})
        
        # Update metadata
        if name is not None:
            meta["name"] = name
        if description is not None:
            meta["description"] = description
        meta["modified_at"] = datetime.now().isoformat()
        
        # Create new GPX content
        route_name = meta.get("name", os.path.splitext(filename)[0])
        route_description = meta.get("description", "")
        gpx_content = self.gpx_service.create_gpx_from_waypoints(
            waypoints, route_name, route_description
        )
        
        # Save updated file
        self.gpx_service.save_gpx_file(filename, gpx_content)
        
        # Update metadata
        metadata[filename] = meta
        self._write_metadata(metadata)
        
        logging.info(f"Updated route: {filename}")
        
        return self.get_route(filename)
    
    def delete_route(self, filename: str) -> bool:
        """Delete a route and its versions."""
        if not self.gpx_service.delete_gpx_file(filename):
            return False
        
        # Remove from metadata
        metadata = self._read_metadata()
        if filename in metadata:
            del metadata[filename]
            self._write_metadata(metadata)
        
        # Delete version files
        version_files = self._get_version_files(filename)
        for version_file in version_files:
            self.gpx_service.delete_gpx_file(version_file)
        
        logging.info(f"Deleted route: {filename}")
        return True
    
    def toggle_favorite(self, filename: str) -> Optional[Dict]:
        """Toggle favorite status of a route."""
        if not os.path.exists(os.path.join(self.gpx_service.gpx_folder, filename)):
            return None
        
        metadata = self._read_metadata()
        if filename not in metadata:
            metadata[filename] = {"name": os.path.splitext(filename)[0]}
        
        current_status = metadata[filename].get("is_favorite", False)
        metadata[filename]["is_favorite"] = not current_status
        metadata[filename]["modified_at"] = datetime.now().isoformat()
        
        self._write_metadata(metadata)
        
        logging.info(f"Toggled favorite for {filename} to {not current_status}")
        
        return {
            "filename": filename,
            "is_favorite": not current_status
        }
    
    def create_version_backup(self, filename: str, route_data: Dict) -> str:
        """Create a versioned backup of a route before modification."""
        base_name = os.path.splitext(filename)[0]
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        version_filename = f"{base_name}_v_{timestamp}.gpx"
        
        # Create GPX content from current route data
        gpx_content = self.gpx_service.create_gpx_from_waypoints(
            route_data["waypoints"],
            f"{route_data['name']} (Version {timestamp})",
            route_data.get("description", "")
        )
        
        self.gpx_service.save_gpx_file(version_filename, gpx_content)
        
        # Update metadata for version
        metadata = self._read_metadata()
        metadata[version_filename] = {
            "name": f"{route_data['name']} (Version {timestamp})",
            "description": f"Backup version created on {timestamp}",
            "route_type": route_data.get("route_type", "cycling"),
            "is_favorite": False,
            "is_version": True,
            "original_file": filename,
            "created_at": datetime.now().isoformat()
        }
        self._write_metadata(metadata)
        
        logging.info(f"Created version backup: {version_filename}")
        return version_filename
    
    def get_route_versions(self, filename: str) -> List[Dict]:
        """Get all versions of a route."""
        base_name = os.path.splitext(filename)[0]
        version_files = self._get_version_files(filename)
        
        versions = []
        metadata = self._read_metadata()
        
        for version_file in sorted(version_files, reverse=True):  # Newest first
            if os.path.exists(os.path.join(self.gpx_service.gpx_folder, version_file)):
                meta = metadata.get(version_file, {})
                versions.append({
                    "filename": version_file,
                    "name": meta.get("name", version_file),
                    "created_at": meta.get("created_at"),
                    "description": meta.get("description", "")
                })
        
        return versions
    
    def _get_version_files(self, filename: str) -> List[str]:
        """Get all version files for a given route."""
        base_name = os.path.splitext(filename)[0]
        version_pattern = f"{base_name}_v_"
        
        return [f for f in os.listdir(self.gpx_service.gpx_folder)
                if f.startswith(version_pattern) and f.endswith('.gpx')]