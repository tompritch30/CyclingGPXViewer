import requests
import logging
from typing import List, Dict, Optional
from urllib.parse import quote

class GeocodingService:
    """Service for geocoding addresses to coordinates."""
    
    def __init__(self):
        # Using Nominatim (OpenStreetMap's geocoding service)
        self.base_url = "https://nominatim.openstreetmap.org/search"
        self.headers = {
            'User-Agent': 'GPX-Route-Editor/2.0'
        }
    
    def geocode(self, query: str, limit: int = 5) -> List[Dict]:
        """
        Geocode an address or place name to coordinates.
        
        Args:
            query: Search query (address, place name, etc.)
            limit: Maximum number of results to return
            
        Returns:
            List of geocoding results with coordinates and details
        """
        if not query.strip():
            return []
        
        params = {
            'q': query.strip(),
            'format': 'json',
            'limit': limit,
            'addressdetails': 1,
            'extratags': 1,
            'namedetails': 1
        }
        
        try:
            response = requests.get(
                self.base_url,
                params=params,
                headers=self.headers,
                timeout=10
            )
            response.raise_for_status()
            
            results = response.json()
            
            return [self._format_result(result) for result in results]
            
        except requests.RequestException as e:
            logging.error(f"Geocoding request failed for '{query}': {e}")
            return []
        except Exception as e:
            logging.error(f"Geocoding error for '{query}': {e}")
            return []
    
    def _format_result(self, result: Dict) -> Dict:
        """Format a geocoding result for consistent API response."""
        address = result.get('address', {})
        
        # Build display name with relevant components
        name_parts = []
        if address.get('house_number') and address.get('road'):
            name_parts.append(f"{address['house_number']} {address['road']}")
        elif address.get('road'):
            name_parts.append(address['road'])
        
        if address.get('suburb'):
            name_parts.append(address['suburb'])
        elif address.get('neighbourhood'):
            name_parts.append(address['neighbourhood'])
        
        if address.get('city'):
            name_parts.append(address['city'])
        elif address.get('town'):
            name_parts.append(address['town'])
        elif address.get('village'):
            name_parts.append(address['village'])
        
        if address.get('country'):
            name_parts.append(address['country'])
        
        display_name = ', '.join(name_parts) if name_parts else result.get('display_name', '')
        
        return {
            'lat': float(result['lat']),
            'lon': float(result['lon']),
            'display_name': display_name,
            'full_address': result.get('display_name', ''),
            'type': result.get('type', 'unknown'),
            'class': result.get('class', 'unknown'),
            'importance': float(result.get('importance', 0)),
            'place_id': result.get('place_id'),
            'address_components': {
                'house_number': address.get('house_number'),
                'road': address.get('road'),
                'suburb': address.get('suburb'),
                'city': address.get('city') or address.get('town') or address.get('village'),
                'postcode': address.get('postcode'),
                'country': address.get('country'),
                'country_code': address.get('country_code')
            }
        }
    
    def reverse_geocode(self, lat: float, lon: float) -> Optional[Dict]:
        """
        Reverse geocode coordinates to an address.
        
        Args:
            lat: Latitude
            lon: Longitude
            
        Returns:
            Address information or None if not found
        """
        reverse_url = "https://nominatim.openstreetmap.org/reverse"
        
        params = {
            'lat': lat,
            'lon': lon,
            'format': 'json',
            'addressdetails': 1
        }
        
        try:
            response = requests.get(
                reverse_url,
                params=params,
                headers=self.headers,
                timeout=10
            )
            response.raise_for_status()
            
            result = response.json()
            if result:
                return self._format_result(result)
            
            return None
            
        except requests.RequestException as e:
            logging.error(f"Reverse geocoding failed for {lat},{lon}: {e}")
            return None
        except Exception as e:
            logging.error(f"Reverse geocoding error for {lat},{lon}: {e}")
            return None