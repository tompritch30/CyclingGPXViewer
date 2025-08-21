import os
import logging
import gpxpy
import gpxpy.gpx
import math
from datetime import datetime
from typing import List, Dict, Optional, Tuple

class GPXService:
    """Service for GPX file operations."""
    
    def __init__(self, gpx_folder: str):
        self.gpx_folder = gpx_folder
        
    def parse_gpx_file(self, filepath: str) -> Optional[Dict]:
        """Parse a GPX file and return its data structure."""
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
                
                # Extract waypoints
                waypoints = []
                for wp in gpx.waypoints:
                    waypoint_name = wp.name or f"Waypoint {len(waypoints) + 1}"
                    waypoints.append([wp.latitude, wp.longitude, waypoint_name])
                
                # If no waypoints but we have tracks, create waypoints from track points
                if not waypoints and tracks:
                    for i, track in enumerate(tracks):
                        if track and len(track) >= 2:
                            # Use start and end points
                            waypoints.append([track[0][0], track[0][1], f"Start"])
                            waypoints.append([track[-1][0], track[-1][1], f"End"])
                
                return {
                    "tracks": tracks,
                    "waypoints": waypoints,
                    "name": gpx.name or os.path.splitext(os.path.basename(filepath))[0],
                    "description": gpx.description or ""
                }
        except Exception as e:
            logging.error(f"Failed to parse GPX {os.path.basename(filepath)}: {e}")
            return None
    
    def create_gpx_from_waypoints(self, waypoints: List[Tuple], name: str = "Route", 
                                description: str = "") -> str:
        """Generate GPX XML content from waypoints."""
        gpx = gpxpy.gpx.GPX()
        
        # Set metadata
        gpx.name = name
        gpx.description = description or f"Route created with GPX Editor - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
        gpx.creator = "GPX Route Editor"
        
        # Create track
        gpx_track = gpxpy.gpx.GPXTrack()
        gpx_track.name = name
        gpx.tracks.append(gpx_track)
        
        gpx_segment = gpxpy.gpx.GPXTrackSegment()
        gpx_track.segments.append(gpx_segment)
        
        # Add points
        for i, point in enumerate(waypoints):
            lat, lon = point[0], point[1]
            point_name = point[2] if len(point) > 2 else f"Point {i+1}"
            
            # Add to track segment
            track_point = gpxpy.gpx.GPXTrackPoint(latitude=lat, longitude=lon)
            gpx_segment.points.append(track_point)
            
            # Add as waypoint (only start and end for cleaner files)
            if i == 0 or i == len(waypoints) - 1 or len(waypoints) <= 5:
                waypoint = gpxpy.gpx.GPXWaypoint(
                    latitude=lat, 
                    longitude=lon, 
                    name=point_name
                )
                gpx.waypoints.append(waypoint)
        
        return gpx.to_xml()
    
    def save_gpx_file(self, filename: str, gpx_content: str) -> str:
        """Save GPX content to file."""
        filepath = os.path.join(self.gpx_folder, filename)
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(gpx_content)
        return filepath
    
    def delete_gpx_file(self, filename: str) -> bool:
        """Delete a GPX file."""
        filepath = os.path.join(self.gpx_folder, filename)
        if os.path.exists(filepath):
            os.remove(filepath)
            return True
        return False
    
    def calculate_route_stats(self, waypoints: List[Tuple]) -> Dict:
        """Calculate route statistics."""
        if len(waypoints) < 2:
            return {
                "distance_km": 0,
                "waypoint_count": len(waypoints),
                "bounds": None
            }
        
        total_distance = 0
        min_lat = min_lon = float('inf')
        max_lat = max_lon = float('-inf')
        
        for i, point in enumerate(waypoints):
            lat, lon = point[0], point[1]
            
            # Update bounds
            min_lat = min(min_lat, lat)
            max_lat = max(max_lat, lat)
            min_lon = min(min_lon, lon)
            max_lon = max(max_lon, lon)
            
            # Calculate distance
            if i > 0:
                prev_lat, prev_lon = waypoints[i-1][0], waypoints[i-1][1]
                total_distance += self._haversine_distance(prev_lat, prev_lon, lat, lon)
        
        return {
            "distance_km": round(total_distance / 1000, 2),
            "waypoint_count": len(waypoints),
            "bounds": {
                "north": max_lat,
                "south": min_lat,
                "east": max_lon,
                "west": min_lon
            }
        }
    
    def _haversine_distance(self, lat1: float, lon1: float, lat2: float, lon2: float) -> float:
        """Calculate distance between two points using Haversine formula."""
        R = 6371000  # Earth's radius in meters
        
        lat1_rad = math.radians(lat1)
        lat2_rad = math.radians(lat2)
        delta_lat = math.radians(lat2 - lat1)
        delta_lon = math.radians(lon2 - lon1)
        
        a = (math.sin(delta_lat/2)**2 + 
             math.cos(lat1_rad) * math.cos(lat2_rad) * math.sin(delta_lon/2)**2)
        c = 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))
        
        return R * c
    
    def get_route_bounds_overlap(self, route_bounds: Dict, map_bounds: Dict, 
                               min_overlap: float = 0.6) -> bool:
        """Check if route has sufficient overlap with map bounds."""
        if not route_bounds or not map_bounds:
            return True
        
        # Calculate intersection
        intersection = {
            'north': min(route_bounds['north'], map_bounds['north']),
            'south': max(route_bounds['south'], map_bounds['south']),
            'east': min(route_bounds['east'], map_bounds['east']),
            'west': max(route_bounds['west'], map_bounds['west'])
        }
        
        # Check if intersection exists
        if (intersection['north'] <= intersection['south'] or 
            intersection['east'] <= intersection['west']):
            return False
        
        # Calculate areas
        route_area = ((route_bounds['north'] - route_bounds['south']) * 
                     (route_bounds['east'] - route_bounds['west']))
        intersection_area = ((intersection['north'] - intersection['south']) * 
                           (intersection['east'] - intersection['west']))
        
        if route_area <= 0:
            return False
        
        overlap_ratio = intersection_area / route_area
        return overlap_ratio >= min_overlap