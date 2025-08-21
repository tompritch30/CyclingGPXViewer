class GPXEditor {
    constructor() {
        this.map = null;
        this.routingControl = null;
        this.currentRoute = null;
        this.routes = [];
        this.isEditMode = false;
        this.isAddingWaypoints = false;
        this.waypointMarkers = [];
        
        // London coordinates - default center
        this.defaultCenter = [51.5074, -0.1278];
        this.defaultZoom = 11;
        
        // Route colors for better visibility on light maps
        this.routeColors = [
            '#0ea5e9', // bright blue
            '#ec4899', // bright pink
            '#22c55e', // bright green
            '#f59e0b', // bright orange
            '#8b5cf6', // bright purple
            '#ef4444'  // bright red
        ];
        
        this.init();
    }

    async init() {
        try {
            this.initMap();
            this.setupEventListeners();
            await this.loadRoutes();
            this.showToast('Welcome to GPX Route Editor', 'Ready to create and edit cycling routes!', 'success');
        } catch (error) {
            console.error('Failed to initialize:', error);
            this.showToast('Initialization Error', 'Failed to start the application', 'error');
        }
    }

    initMap() {
        // Initialize map with light theme for better route visibility
        this.map = L.map('map').setView(this.defaultCenter, this.defaultZoom);
        
        // Use CartoDB Positron for a clean, light background
        const lightTile = L.tileLayer('https://{s}.basemaps.cartocdn.com/light_all/{z}/{x}/{y}{r}.png', {
            attribution: '© OpenStreetMap contributors © CARTO',
            subdomains: 'abcd',
            maxZoom: 19
        });

        // Alternative cycling layer for detailed view
        const cyclingTile = L.tileLayer('https://{s}.tile-cyclosm.openstreetmap.fr/cyclosm/{z}/{x}/{y}.png', {
            maxZoom: 20,
            attribution: '© OpenStreetMap contributors, © CyclOSM'
        });

        // Default to light theme
        lightTile.addTo(this.map);

        // Layer control
        const baseMaps = {
            "Light Theme": lightTile,
            "Cycling Map": cyclingTile
        };
        L.control.layers(baseMaps).addTo(this.map);

        // Map event listeners
        this.map.on('moveend zoomend', () => this.onMapBoundsChange());
        this.map.on('click', (e) => this.onMapClick(e));
    }

    setupEventListeners() {
        // Route management
        document.getElementById('newRouteBtn').addEventListener('click', () => this.startNewRoute());
        document.getElementById('importBtn').addEventListener('click', () => this.showImportModal());
        document.getElementById('saveRouteBtn').addEventListener('click', () => this.showSaveModal());
        document.getElementById('cancelEditBtn').addEventListener('click', () => this.cancelEdit());

        // Map controls
        document.getElementById('locateBtn').addEventListener('click', () => this.locateUser());
        document.getElementById('fitBoundsBtn').addEventListener('click', () => this.fitAllRoutes());

        // Edit mode controls
        document.getElementById('addWaypointBtn').addEventListener('click', () => this.toggleWaypointMode());
        document.getElementById('searchAddressBtn').addEventListener('click', () => this.showAddressSearchModal());
        document.getElementById('clearWaypointsBtn').addEventListener('click', () => this.clearAllWaypoints());

        // Search and filters
        document.getElementById('routeSearch').addEventListener('input', (e) => this.filterRoutes(e.target.value));
        document.getElementById('showFavoritesOnly').addEventListener('change', (e) => this.filterRoutes());

        // Modal handlers
        this.setupModalHandlers();

        // Keyboard shortcuts
        document.addEventListener('keydown', (e) => this.handleKeyboardShortcuts(e));
    }

    setupModalHandlers() {
        // Save modal
        document.getElementById('closeSaveModal').addEventListener('click', () => this.hideSaveModal());
        document.getElementById('cancelSaveBtn').addEventListener('click', () => this.hideSaveModal());
        document.getElementById('confirmSaveBtn').addEventListener('click', () => this.saveRoute());

        // Address search modal
        document.getElementById('closeSearchModal').addEventListener('click', () => this.hideAddressSearchModal());
        document.getElementById('cancelSearchBtn').addEventListener('click', () => this.hideAddressSearchModal());
        document.getElementById('searchBtn').addEventListener('click', () => this.searchAddress());
        document.getElementById('addressInput').addEventListener('keydown', (e) => {
            if (e.key === 'Enter') this.searchAddress();
        });

        // Import modal
        document.getElementById('closeImportModal').addEventListener('click', () => this.hideImportModal());
        
        const fileInput = document.getElementById('gpxFileInput');
        const uploadArea = document.getElementById('fileUploadArea');
        
        uploadArea.addEventListener('click', () => fileInput.click());
        uploadArea.addEventListener('dragover', (e) => this.handleDragOver(e));
        uploadArea.addEventListener('drop', (e) => this.handleFileDrop(e));
        fileInput.addEventListener('change', (e) => this.handleFileSelect(e));

        // Close modals on outside click
        document.addEventListener('click', (e) => {
            if (e.target.classList.contains('modal-overlay')) {
                this.hideAllModals();
            }
        });
    }

    async loadRoutes() {
        try {
            document.getElementById('routesList').innerHTML = `
                <div class="loading-spinner">
                    <i class="fas fa-spinner fa-spin"></i>
                    <span>Loading routes...</span>
                </div>
            `;

            const bounds = this.map.getBounds();
            const boundsParam = {
                north: bounds.getNorth(),
                south: bounds.getSouth(),
                east: bounds.getEast(),
                west: bounds.getWest()
            };

            const response = await fetch(`/api/routes?${new URLSearchParams(boundsParam)}`);
            if (!response.ok) throw new Error('Failed to load routes');
            
            const data = await response.json();
            this.routes = data.routes;
            this.renderRoutesList();
            this.displayRoutesOverview();
        } catch (error) {
            console.error('Error loading routes:', error);
            this.showToast('Error', 'Failed to load routes', 'error');
        }
    }

    renderRoutesList() {
        const container = document.getElementById('routesList');
        const searchTerm = document.getElementById('routeSearch').value.toLowerCase();
        const showFavoritesOnly = document.getElementById('showFavoritesOnly').checked;
        
        let filteredRoutes = this.routes;
        
        if (searchTerm) {
            filteredRoutes = filteredRoutes.filter(route => 
                route.name.toLowerCase().includes(searchTerm) ||
                (route.description && route.description.toLowerCase().includes(searchTerm))
            );
        }
        
        if (showFavoritesOnly) {
            filteredRoutes = filteredRoutes.filter(route => route.is_favorite);
        }

        if (filteredRoutes.length === 0) {
            container.innerHTML = `
                <div class="empty-state">
                    <i class="fas fa-map"></i>
                    <p>No routes found</p>
                    <small>Try adjusting your search or create a new route</small>
                </div>
            `;
            return;
        }

        container.innerHTML = filteredRoutes.map((route, index) => `
            <div class="route-item ${this.currentRoute?.filename === route.filename ? 'active' : ''}" 
                 data-filename="${route.filename}">
                <div class="route-actions">
                    <button class="route-action-btn favorite-btn ${route.is_favorite ? 'active' : ''}" 
                            onclick="editor.toggleFavorite('${route.filename}')" title="Toggle favorite">
                        <i class="fas fa-star"></i>
                    </button>
                    <button class="route-action-btn delete-btn" 
                            onclick="editor.deleteRoute('${route.filename}')" title="Delete route">
                        <i class="fas fa-trash"></i>
                    </button>
                </div>
                
                <div class="route-header">
                    <div class="route-name">${route.name}</div>
                </div>
                
                ${route.description ? `<div class="route-description">${route.description}</div>` : ''}
                
                <div class="route-meta">
                    <div class="route-stats-inline">
                        <span><i class="fas fa-map-marker-alt"></i> ${route.stats.waypoint_count}</span>
                        <span><i class="fas fa-route"></i> ${route.stats.distance_km} km</span>
                        <span><i class="fas fa-bicycle"></i> ${route.route_type}</span>
                    </div>
                </div>
                
                ${route.version_count > 0 ? `<div class="version-info">${route.version_count} versions</div>` : ''}
            </div>
        `).join('');

        // Add click handlers
        container.querySelectorAll('.route-item').forEach(item => {
            item.addEventListener('click', (e) => {
                if (!e.target.closest('.route-actions')) {
                    this.loadRoute(item.dataset.filename);
                }
            });
        });
    }

    displayRoutesOverview() {
        this.clearMapRoutes();
        
        if (this.routes.length === 0) return;

        const bounds = new L.LatLngBounds();
        
        this.routes.forEach((route, index) => {
            if (route.tracks && route.tracks.length > 0) {
                const color = this.routeColors[index % this.routeColors.length];
                const trackPoints = route.tracks.flat();
                
                if (trackPoints.length > 0) {
                    const polyline = L.polyline(trackPoints, {
                        color: color,
                        weight: 4,
                        opacity: 0.7,
                        smoothFactor: 1.0
                    });
                    
                    polyline.bindPopup(`
                        <div style="text-align: center; min-width: 150px;">
                            <strong>${route.name}</strong><br>
                            <small>${route.stats.distance_km} km • ${route.stats.waypoint_count} waypoints</small>
                            <br><br>
                            <button onclick="editor.loadRoute('${route.filename}')" 
                                    style="background: #0ea5e9; color: white; border: none; padding: 4px 8px; border-radius: 4px; cursor: pointer;">
                                Edit Route
                            </button>
                        </div>
                    `);
                    
                    polyline.addTo(this.map);
                    bounds.extend(polyline.getBounds());
                }
            }
        });

        if (bounds.isValid()) {
            this.map.fitBounds(bounds, { padding: [20, 20] });
        }
    }

    async loadRoute(filename) {
        try {
            const response = await fetch(`/api/route/${filename}`);
            if (!response.ok) throw new Error('Failed to load route');
            
            const route = await response.json();
            this.currentRoute = route;
            
            this.clearMapRoutes();
            this.enterEditMode();
            this.setupRouteEditing();
            this.updateRouteDetails();
            
            // Highlight active route in list
            document.querySelectorAll('.route-item').forEach(item => {
                item.classList.toggle('active', item.dataset.filename === filename);
            });
            
        } catch (error) {
            console.error('Error loading route:', error);
            this.showToast('Error', 'Failed to load route', 'error');
        }
    }

    setupRouteEditing() {
        if (!this.currentRoute || !this.currentRoute.waypoints) return;

        const waypoints = this.currentRoute.waypoints.map(wp => L.latLng(wp[0], wp[1]));
        
        this.routingControl = L.Routing.control({
            waypoints: waypoints,
            routeWhileDragging: true,
            addWaypoints: false,
            router: L.Routing.osrmv1({
                serviceUrl: 'https://router.project-osrm.org/route/v1',
                profile: 'cycling'
            }),
            lineOptions: {
                styles: [{
                    color: this.routeColors[0],
                    weight: 6,
                    opacity: 0.8
                }],
                extendToWaypoints: true,
                missingRouteTolerance: 0
            },
            createMarker: (i, waypoint, n) => this.createWaypointMarker(i, waypoint, n),
            show: false,
            fitSelectedRoutes: true
        }).addTo(this.map);

        this.routingControl.on('routesfound', () => {
            this.updateRouteStats();
        });

        this.updateWaypointsList();
    }

    createWaypointMarker(i, waypoint, n) {
        const marker = L.marker(waypoint.latLng, {
            draggable: true,
            icon: L.divIcon({
                className: 'waypoint-marker',
                html: `<div class="waypoint-marker">${i + 1}</div>`,
                iconSize: [30, 30],
                iconAnchor: [15, 15]
            })
        });

        const waypointName = this.currentRoute.waypoints[i]?.[2] || `Waypoint ${i + 1}`;
        
        marker.bindPopup(`
            <div style="text-align: center;">
                <strong>${waypointName}</strong><br>
                <small>${waypoint.latLng.lat.toFixed(4)}, ${waypoint.latLng.lng.toFixed(4)}</small><br>
                <button onclick="editor.removeWaypoint(${i})" 
                        style="background: #ef4444; color: white; border: none; padding: 4px 8px; border-radius: 4px; cursor: pointer; margin-top: 5px;">
                    Remove
                </button>
            </div>
        `);

        marker.on('dragend', () => {
            this.updateRouteStats();
            this.updateWaypointsList();
        });

        this.waypointMarkers.push(marker);
        return marker;
    }

    startNewRoute() {
        this.currentRoute = {
            filename: null,
            name: 'New Route',
            waypoints: [],
            tracks: [],
            route_type: 'cycling'
        };
        
        this.clearMapRoutes();
        this.enterEditMode();
        this.enableWaypointMode();
        
        this.routingControl = L.Routing.control({
            waypoints: [],
            routeWhileDragging: true,
            addWaypoints: false,
            router: L.Routing.osrmv1({
                serviceUrl: 'https://router.project-osrm.org/route/v1',
                profile: 'cycling'
            }),
            lineOptions: {
                styles: [{
                    color: '#22c55e',
                    weight: 6,
                    opacity: 0.8
                }]
            },
            createMarker: (i, waypoint, n) => this.createWaypointMarker(i, waypoint, n),
            show: false
        }).addTo(this.map);

        this.routingControl.on('routesfound', () => {
            this.updateRouteStats();
        });

        this.updateWaypointsList();
        this.showToast('New Route', 'Click on the map to add waypoints', 'success');
    }

    enterEditMode() {
        this.isEditMode = true;
        document.getElementById('editorControls').style.display = 'flex';
        document.getElementById('editingOverlay').style.display = 'block';
        document.getElementById('rightSidebar').style.display = 'flex';
        document.querySelector('.sidebar-left').style.width = '250px';
    }

    exitEditMode() {
        this.isEditMode = false;
        this.isAddingWaypoints = false;
        document.getElementById('editorControls').style.display = 'none';
        document.getElementById('editingOverlay').style.display = 'none';
        document.getElementById('rightSidebar').style.display = 'none';
        document.querySelector('.sidebar-left').style.width = '300px';
        
        this.clearMapRoutes();
        this.displayRoutesOverview();
        this.currentRoute = null;
        
        // Reset active route in list
        document.querySelectorAll('.route-item').forEach(item => {
            item.classList.remove('active');
        });
    }

    cancelEdit() {
        if (confirm('Are you sure you want to cancel editing? Any unsaved changes will be lost.')) {
            this.exitEditMode();
        }
    }

    enableWaypointMode() {
        this.isAddingWaypoints = true;
        const btn = document.getElementById('addWaypointBtn');
        btn.classList.add('btn-success');
        btn.innerHTML = '<i class="fas fa-map-marker-alt"></i> Click map to add waypoint';
        document.getElementById('editingStatusText').textContent = 'Adding waypoints - Click on map';
        this.map.getContainer().style.cursor = 'crosshair';
    }

    disableWaypointMode() {
        this.isAddingWaypoints = false;
        const btn = document.getElementById('addWaypointBtn');
        btn.classList.remove('btn-success');
        btn.innerHTML = '<i class="fas fa-map-marker-alt"></i> Click map to add waypoint';
        document.getElementById('editingStatusText').textContent = 'Editing Mode';
        this.map.getContainer().style.cursor = '';
    }

    toggleWaypointMode() {
        if (this.isAddingWaypoints) {
            this.disableWaypointMode();
        } else {
            this.enableWaypointMode();
        }
    }

    onMapClick(e) {
        if (this.isEditMode && this.isAddingWaypoints) {
            this.addWaypoint(e.latlng);
        }
    }

    addWaypoint(latlng) {
        if (!this.routingControl) return;

        const waypoints = this.routingControl.getWaypoints();
        waypoints.push(L.Routing.waypoint(latlng));
        this.routingControl.setWaypoints(waypoints);
        
        // Update current route data
        if (!this.currentRoute.waypoints) this.currentRoute.waypoints = [];
        this.currentRoute.waypoints.push([latlng.lat, latlng.lng]);
        
        this.updateWaypointsList();
        this.showToast('Waypoint Added', `Added waypoint at ${latlng.lat.toFixed(4)}, ${latlng.lng.toFixed(4)}`, 'success');
    }

    removeWaypoint(index) {
        if (!this.routingControl) return;

        const waypoints = this.routingControl.getWaypoints();
        waypoints.splice(index, 1);
        this.routingControl.setWaypoints(waypoints);
        
        if (this.currentRoute.waypoints) {
            this.currentRoute.waypoints.splice(index, 1);
        }
        
        this.updateWaypointsList();
        this.showToast('Waypoint Removed', 'Waypoint has been removed', 'warning');
    }

    clearAllWaypoints() {
        if (confirm('Remove all waypoints?')) {
            if (this.routingControl) {
                this.routingControl.setWaypoints([]);
            }
            if (this.currentRoute) {
                this.currentRoute.waypoints = [];
            }
            this.updateWaypointsList();
            this.showToast('All Waypoints Cleared', 'All waypoints have been removed', 'warning');
        }
    }

    updateWaypointsList() {
        const container = document.getElementById('waypointsList');
        
        if (!this.currentRoute || !this.currentRoute.waypoints || this.currentRoute.waypoints.length === 0) {
            container.innerHTML = `
                <div class="empty-state">
                    <i class="fas fa-map-marker-alt"></i>
                    <p>No waypoints yet</p>
                    <small>Click on the map to add waypoints</small>
                </div>
            `;
            return;
        }

        container.innerHTML = this.currentRoute.waypoints.map((waypoint, index) => `
            <div class="waypoint-item" data-index="${index}">
                <div class="waypoint-drag-handle">
                    <i class="fas fa-grip-vertical"></i>
                </div>
                <div class="waypoint-info">
                    <div class="waypoint-name">Waypoint ${index + 1}</div>
                    <div class="waypoint-coords">${waypoint[0].toFixed(4)}, ${waypoint[1].toFixed(4)}</div>
                </div>
                <div class="waypoint-actions">
                    <button class="route-action-btn delete-btn" onclick="editor.removeWaypoint(${index})" title="Remove waypoint">
                        <i class="fas fa-trash"></i>
                    </button>
                </div>
            </div>
        `).join('');
    }

    updateRouteStats() {
        if (!this.routingControl) return;

        const routes = this.routingControl.getRoutes();
        if (routes.length > 0) {
            const route = routes[0];
            const distance = (route.summary.totalDistance / 1000).toFixed(1);
            const waypoints = this.routingControl.getWaypoints().length;
            
            document.getElementById('routeDistance').textContent = `${distance} km`;
            document.getElementById('waypointCount').textContent = waypoints;
        }
    }

    updateRouteDetails() {
        if (!this.currentRoute) return;

        document.getElementById('routeDetailsTitle').textContent = this.currentRoute.name;
        document.getElementById('routeDistance').textContent = this.currentRoute.stats?.distance_km + ' km' || '0 km';
        document.getElementById('waypointCount').textContent = this.currentRoute.waypoints?.length || 0;
        document.getElementById('routeType').textContent = this.currentRoute.route_type || 'cycling';
    }

    clearMapRoutes() {
        if (this.routingControl) {
            this.map.removeControl(this.routingControl);
            this.routingControl = null;
        }
        
        // Clear any polylines
        this.map.eachLayer(layer => {
            if (layer instanceof L.Polyline && !(layer instanceof L.Marker)) {
                this.map.removeLayer(layer);
            }
        });
        
        this.waypointMarkers = [];
    }

    // Modal Methods
    showSaveModal() {
        if (!this.currentRoute) return;
        
        document.getElementById('routeName').value = this.currentRoute.name;
        document.getElementById('routeDescription').value = this.currentRoute.description || '';
        document.getElementById('routeTypeSelect').value = this.currentRoute.route_type;
        document.getElementById('saveRouteModal').style.display = 'flex';
    }

    hideSaveModal() {
        document.getElementById('saveRouteModal').style.display = 'none';
    }

    showAddressSearchModal() {
        document.getElementById('addressSearchModal').style.display = 'flex';
        document.getElementById('addressInput').focus();
    }

    hideAddressSearchModal() {
        document.getElementById('addressSearchModal').style.display = 'none';
        document.getElementById('searchResults').style.display = 'none';
        document.getElementById('addressInput').value = '';
    }

    showImportModal() {
        document.getElementById('importModal').style.display = 'flex';
    }

    hideImportModal() {
        document.getElementById('importModal').style.display = 'none';
    }

    hideAllModals() {
        this.hideSaveModal();
        this.hideAddressSearchModal();
        this.hideImportModal();
    }

    async saveRoute() {
        const name = document.getElementById('routeName').value.trim();
        const description = document.getElementById('routeDescription').value.trim();
        const routeType = document.getElementById('routeTypeSelect').value;

        if (!name) {
            this.showToast('Error', 'Please enter a route name', 'error');
            return;
        }

        if (!this.currentRoute.waypoints || this.currentRoute.waypoints.length < 2) {
            this.showToast('Error', 'Please add at least 2 waypoints', 'error');
            return;
        }

        try {
            // Get current waypoints from routing control
            const waypoints = this.routingControl.getWaypoints().map(wp => [wp.latLng.lat, wp.latLng.lng]);
            
            const routeData = {
                name: name,
                description: description,
                type: routeType,
                waypoints: waypoints
            };

            let response;
            if (this.currentRoute.filename) {
                // Update existing route
                response = await fetch(`/api/route/${this.currentRoute.filename}`, {
                    method: 'PUT',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(routeData)
                });
            } else {
                // Create new route
                response = await fetch('/api/routes', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(routeData)
                });
            }

            if (!response.ok) throw new Error('Failed to save route');
            
            const savedRoute = await response.json();
            this.currentRoute = savedRoute;
            
            await this.loadRoutes(); // Refresh route list
            this.hideSaveModal();
            this.exitEditMode();
            this.showToast('Route Saved', `${name} has been saved successfully`, 'success');

        } catch (error) {
            console.error('Error saving route:', error);
            this.showToast('Error', 'Failed to save route', 'error');
        }
    }

    async searchAddress() {
        const query = document.getElementById('addressInput').value.trim();
        if (!query) return;

        try {
            const response = await fetch(`/api/geocode?q=${encodeURIComponent(query)}`);
            if (!response.ok) throw new Error('Geocoding failed');
            
            const data = await response.json();
            const results = data.results;

            const container = document.getElementById('resultsList');
            document.getElementById('searchResults').style.display = 'block';

            if (results.length === 0) {
                container.innerHTML = '<div class="empty-state"><p>No results found</p></div>';
                return;
            }

            container.innerHTML = results.map(result => `
                <div class="search-result-item" onclick="editor.selectSearchResult(${result.lat}, ${result.lon}, '${result.display_name.replace(/'/g, "\\'")}')">
                    <div class="result-name">${result.display_name.split(',')[0]}</div>
                    <div class="result-address">${result.full_address}</div>
                </div>
            `).join('');

        } catch (error) {
            console.error('Geocoding error:', error);
            this.showToast('Error', 'Failed to search address', 'error');
        }
    }

    selectSearchResult(lat, lon, name) {
        const latlng = L.latLng(lat, lon);
        this.map.setView(latlng, 15);
        this.addWaypoint(latlng);
        this.hideAddressSearchModal();
        this.showToast('Waypoint Added', `Added waypoint at ${name}`, 'success');
    }

    // File handling
    handleDragOver(e) {
        e.preventDefault();
        e.stopPropagation();
        document.getElementById('fileUploadArea').classList.add('dragover');
    }

    handleFileDrop(e) {
        e.preventDefault();
        e.stopPropagation();
        document.getElementById('fileUploadArea').classList.remove('dragover');
        
        const files = e.dataTransfer.files;
        if (files.length > 0 && files[0].name.endsWith('.gpx')) {
            this.processGPXFile(files[0]);
        }
    }

    handleFileSelect(e) {
        const file = e.target.files[0];
        if (file && file.name.endsWith('.gpx')) {
            this.processGPXFile(file);
        }
    }

    async processGPXFile(file) {
        try {
            document.getElementById('uploadProgress').style.display = 'block';
            
            const text = await file.text();
            const parser = new DOMParser();
            const gpx = parser.parseFromString(text, 'text/xml');
            
            // Extract waypoints and track points
            const waypoints = this.extractWaypointsFromGPX(gpx);
            const tracks = this.extractTracksFromGPX(gpx);
            const name = this.extractNameFromGPX(gpx) || file.name.replace('.gpx', '');
            
            // Create new route from GPX data
            this.currentRoute = {
                filename: file.name,
                name: name,
                waypoints: waypoints,
                tracks: tracks,
                route_type: 'cycling',
                description: this.extractDescriptionFromGPX(gpx) || ''
            };
            
            this.hideImportModal();
            this.enterEditMode();
            this.setupRouteEditing();
            this.updateRouteDetails();
            
            this.showToast('GPX Imported', `Successfully imported ${name}`, 'success');
            
        } catch (error) {
            console.error('GPX processing error:', error);
            this.showToast('Import Error', 'Failed to process GPX file', 'error');
        } finally {
            document.getElementById('uploadProgress').style.display = 'none';
        }
    }

    extractWaypointsFromGPX(gpx) {
        const waypoints = [];
        const wptElements = gpx.querySelectorAll('wpt');
        
        wptElements.forEach(wpt => {
            const lat = parseFloat(wpt.getAttribute('lat'));
            const lon = parseFloat(wpt.getAttribute('lon'));
            const name = wpt.querySelector('name')?.textContent || '';
            waypoints.push([lat, lon, name]);
        });
        
        return waypoints;
    }

    extractTracksFromGPX(gpx) {
        const tracks = [];
        const trkElements = gpx.querySelectorAll('trk');
        
        trkElements.forEach(trk => {
            const segments = trk.querySelectorAll('trkseg');
            segments.forEach(seg => {
                const points = [];
                const trkpts = seg.querySelectorAll('trkpt');
                
                trkpts.forEach(pt => {
                    const lat = parseFloat(pt.getAttribute('lat'));
                    const lon = parseFloat(pt.getAttribute('lon'));
                    points.push([lat, lon]);
                });
                
                if (points.length > 0) {
                    tracks.push(points);
                }
            });
        });
        
        return tracks;
    }

    extractNameFromGPX(gpx) {
        const nameElement = gpx.querySelector('metadata name, trk name');
        return nameElement?.textContent || null;
    }

    extractDescriptionFromGPX(gpx) {
        const descElement = gpx.querySelector('metadata desc, trk desc');
        return descElement?.textContent || null;
    }

    // Map controls
    async locateUser() {
        if (!navigator.geolocation) {
            this.showToast('Error', 'Geolocation not supported', 'error');
            return;
        }

        try {
            const position = await new Promise((resolve, reject) => {
                navigator.geolocation.getCurrentPosition(resolve, reject, {
                    enableHighAccuracy: true,
                    timeout: 10000,
                    maximumAge: 60000
                });
            });

            const { latitude, longitude } = position.coords;
            this.map.setView([latitude, longitude], 15);
            
            // Add temporary marker
            const marker = L.marker([latitude, longitude])
                .addTo(this.map)
                .bindPopup('Your location')
                .openPopup();
            
            setTimeout(() => this.map.removeLayer(marker), 3000);
            
        } catch (error) {
            console.error('Geolocation error:', error);
            this.showToast('Error', 'Could not get your location', 'error');
        }
    }

    fitAllRoutes() {
        if (this.isEditMode && this.routingControl) {
            // Fit current route
            const waypoints = this.routingControl.getWaypoints().filter(wp => wp.latLng);
            if (waypoints.length > 0) {
                const group = new L.featureGroup(waypoints.map(wp => L.marker(wp.latLng)));
                this.map.fitBounds(group.getBounds(), { padding: [20, 20] });
            }
        } else {
            // Fit all routes overview
            this.displayRoutesOverview();
        }
    }

    onMapBoundsChange() {
        // Could be used to load routes in viewport
        // For now, just log the event
        console.log('Map bounds changed');
    }

    // Route management
    async toggleFavorite(filename) {
        try {
            const response = await fetch(`/api/route/${filename}/favorite`, {
                method: 'POST'
            });
            
            if (!response.ok) throw new Error('Failed to toggle favorite');
            
            const result = await response.json();
            
            // Update local route data
            const route = this.routes.find(r => r.filename === filename);
            if (route) {
                route.is_favorite = result.is_favorite;
            }
            
            this.renderRoutesList();
            this.showToast('Favorite Updated', result.is_favorite ? 'Added to favorites' : 'Removed from favorites', 'success');
            
        } catch (error) {
            console.error('Error toggling favorite:', error);
            this.showToast('Error', 'Failed to update favorite', 'error');
        }
    }

    async deleteRoute(filename) {
        if (!confirm('Are you sure you want to delete this route?')) return;

        try {
            const response = await fetch(`/api/route/${filename}`, {
                method: 'DELETE'
            });
            
            if (!response.ok) throw new Error('Failed to delete route');
            
            // Remove from local array
            const index = this.routes.findIndex(r => r.filename === filename);
            if (index >= 0) {
                this.routes.splice(index, 1);
            }
            
            this.renderRoutesList();
            this.displayRoutesOverview();
            this.showToast('Route Deleted', 'Route has been deleted', 'warning');
            
        } catch (error) {
            console.error('Error deleting route:', error);
            this.showToast('Error', 'Failed to delete route', 'error');
        }
    }

    // Export functionality
    exportRouteAsGPX(route = this.currentRoute) {
        if (!route) return;

        const gpxContent = this.generateGPX(route);
        const blob = new Blob([gpxContent], { type: 'application/gpx+xml' });
        const url = URL.createObjectURL(blob);
        
        const a = document.createElement('a');
        a.href = url;
        a.download = route.filename || `${route.name}.gpx`;
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
        URL.revokeObjectURL(url);
        
        this.showToast('Export Complete', 'GPX file downloaded', 'success');
    }

    generateGPX(route) {
        const waypoints = route.waypoints || [];
        const tracks = route.tracks || [];
        
        let gpx = `<?xml version="1.0" encoding="UTF-8"?>
<gpx version="1.1" creator="GPX Route Editor" xmlns="http://www.topografix.com/GPX/1/1">
    <metadata>
        <name>${this.escapeXml(route.name)}</name>
        ${route.description ? `<desc>${this.escapeXml(route.description)}</desc>` : ''}
        <time>${new Date().toISOString()}</time>
    </metadata>
`;

        // Add waypoints
        waypoints.forEach((wp, index) => {
            const name = wp[2] || `Waypoint ${index + 1}`;
            gpx += `    <wpt lat="${wp[0]}" lon="${wp[1]}">
        <name>${this.escapeXml(name)}</name>
    </wpt>
`;
        });

        // Add tracks
        if (tracks.length > 0) {
            gpx += `    <trk>
        <name>${this.escapeXml(route.name)} Track</name>
        <type>${route.route_type || 'cycling'}</type>
`;
            tracks.forEach(track => {
                gpx += `        <trkseg>
`;
                track.forEach(point => {
                    gpx += `            <trkpt lat="${point[0]}" lon="${point[1]}"></trkpt>
`;
                });
                gpx += `        </trkseg>
`;
            });
            gpx += `    </trk>
`;
        }

        gpx += `</gpx>`;
        return gpx;
    }

    escapeXml(unsafe) {
        return unsafe.replace(/[<>&'"]/g, function (c) {
            switch (c) {
                case '<': return '&lt;';
                case '>': return '&gt;';
                case '&': return '&amp;';
                case '\'': return '&apos;';
                case '"': return '&quot;';
            }
        });
    }

    // Toast notifications
    showToast(title, message, type = 'info') {
        const container = document.getElementById('toastContainer');
        const toast = document.createElement('div');
        toast.className = `toast ${type}`;
        
        const iconMap = {
            success: 'fa-check-circle',
            error: 'fa-exclamation-circle',
            warning: 'fa-exclamation-triangle',
            info: 'fa-info-circle'
        };
        
        toast.innerHTML = `
            <i class="fas ${iconMap[type]} toast-icon"></i>
            <div class="toast-content">
                <div class="toast-title">${title}</div>
                <div class="toast-message">${message}</div>
            </div>
            <button class="toast-close" onclick="this.parentElement.remove()">
                <i class="fas fa-times"></i>
            </button>
        `;
        
        container.appendChild(toast);
        
        // Auto remove after 5 seconds
        setTimeout(() => {
            if (toast.parentElement) {
                toast.remove();
            }
        }, 5000);
    }
}

// Initialize the application
let editor;
document.addEventListener('DOMContentLoaded', () => {
    editor = new GPXEditor();
});

// Global functions for onclick handlers
window.editor = editor;