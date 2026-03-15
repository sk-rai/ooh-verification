import React, { useEffect, useState } from 'react';
import { MapContainer, TileLayer, Marker, Popup, Circle, useMap } from 'react-leaflet';
import MarkerClusterGroup from 'react-leaflet-cluster';
import L from 'leaflet';
import 'leaflet/dist/leaflet.css';

// Fix for default marker icons in React-Leaflet
import icon from 'leaflet/dist/images/marker-icon.png';
import iconShadow from 'leaflet/dist/images/marker-shadow.png';

let DefaultIcon = L.icon({
  iconUrl: icon,
  shadowUrl: iconShadow,
  iconSize: [25, 41],
  iconAnchor: [12, 41],
});

L.Marker.prototype.options.icon = DefaultIcon;

// Custom marker icons for different statuses
const createCustomIcon = (status: string) => {
  const colors = {
    verified: '#10b981', // green
    flagged: '#f59e0b',  // yellow
    rejected: '#ef4444', // red
  };

  const color = colors[status as keyof typeof colors] || '#6b7280';

  return L.divIcon({
    className: 'custom-marker',
    html: `
      <div style="
        background-color: ${color};
        width: 24px;
        height: 24px;
        border-radius: 50%;
        border: 3px solid white;
        box-shadow: 0 2px 4px rgba(0,0,0,0.3);
      "></div>
    `,
    iconSize: [24, 24],
    iconAnchor: [12, 12],
  });
};

interface Photo {
  id: string;
  latitude: number;
  longitude: number;
  verification_status: string;
  captured_at: string;
  vendor_name?: string;
  thumbnail_url?: string;
  distance_from_expected?: number;
}

interface CampaignLocation {
  id: string;
  name: string;
  latitude: number;
  longitude: number;
  verification_radius_meters: number;
}

interface PhotoMapProps {
  photos: Photo[];
  campaignLocations?: CampaignLocation[];
  center?: [number, number];
  zoom?: number;
  onPhotoClick?: (photo: Photo) => void;
}

// Component to fit map bounds to markers
const FitBounds: React.FC<{ photos: Photo[] }> = ({ photos }) => {
  const map = useMap();

  useEffect(() => {
    if (photos.length > 0) {
      const bounds = L.latLngBounds(
        photos.map(p => [p.latitude, p.longitude] as [number, number])
      );
      map.fitBounds(bounds, { padding: [50, 50] });
    }
  }, [photos, map]);

  return null;
};

export const PhotoMap: React.FC<PhotoMapProps> = ({
  photos,
  campaignLocations = [],
  center = [20.5937, 78.9629], // India center as default
  zoom = 5,
  onPhotoClick,
}) => {
  const [selectedPhoto, setSelectedPhoto] = useState<Photo | null>(null);

  const handleMarkerClick = (photo: Photo) => {
    setSelectedPhoto(photo);
    if (onPhotoClick) {
      onPhotoClick(photo);
    }
  };

  return (
    <div className="w-full h-full relative">
      <MapContainer
        center={center}
        zoom={zoom}
        style={{ height: '100%', width: '100%' }}
        className="rounded-lg shadow-lg"
      >
        <TileLayer
          attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
          url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
        />

        {/* Fit bounds to photos */}
        {photos.length > 0 && <FitBounds photos={photos} />}

        {/* Campaign location circles */}
        {campaignLocations.map((location) => (
          <React.Fragment key={location.id}>
            <Circle
              center={[location.latitude, location.longitude]}
              radius={location.verification_radius_meters}
              pathOptions={{
                color: '#3b82f6',
                fillColor: '#3b82f6',
                fillOpacity: 0.1,
                weight: 2,
              }}
            />
            <Marker
              position={[location.latitude, location.longitude]}
              icon={L.divIcon({
                className: 'location-marker',
                html: `
                  <div style="
                    background-color: #3b82f6;
                    color: white;
                    padding: 4px 8px;
                    border-radius: 4px;
                    font-size: 12px;
                    font-weight: bold;
                    white-space: nowrap;
                    box-shadow: 0 2px 4px rgba(0,0,0,0.3);
                  ">${location.name}</div>
                `,
                iconSize: [100, 30],
                iconAnchor: [50, 15],
              })}
            >
              <Popup>
                <div className="p-2">
                  <h3 className="font-bold text-sm">{location.name}</h3>
                  <p className="text-xs text-gray-600">
                    Radius: {location.verification_radius_meters}m
                  </p>
                  <p className="text-xs text-gray-500">
                    {location.latitude.toFixed(6)}, {location.longitude.toFixed(6)}
                  </p>
                </div>
              </Popup>
            </Marker>
          </React.Fragment>
        ))}

        {/* Photo markers with clustering */}
        <MarkerClusterGroup
          chunkedLoading
          maxClusterRadius={50}
          spiderfyOnMaxZoom={true}
          showCoverageOnHover={false}
        >
          {photos.map((photo) => (
            <Marker
              key={photo.id}
              position={[photo.latitude, photo.longitude]}
              icon={createCustomIcon(photo.verification_status)}
              eventHandlers={{
                click: () => handleMarkerClick(photo),
              }}
            >
              <Popup>
                <div className="p-2 min-w-[200px]">
                  {photo.thumbnail_url && (
                    <img
                      src={photo.thumbnail_url}
                      alt="Photo thumbnail"
                      className="w-full h-32 object-cover rounded mb-2"
                    />
                  )}
                  <div className="space-y-1">
                    <div className="flex items-center justify-between">
                      <span className="text-xs font-semibold">Status:</span>
                      <span
                        className={`text-xs px-2 py-1 rounded ${
                          photo.verification_status === 'verified'
                            ? 'bg-green-100 text-green-800'
                            : photo.verification_status === 'flagged'
                            ? 'bg-yellow-100 text-yellow-800'
                            : 'bg-red-100 text-red-800'
                        }`}
                      >
                        {photo.verification_status}
                      </span>
                    </div>
                    {photo.vendor_name && (
                      <p className="text-xs">
                        <span className="font-semibold">Vendor:</span> {photo.vendor_name}
                      </p>
                    )}
                    <p className="text-xs">
                      <span className="font-semibold">Time:</span>{' '}
                      {new Date(photo.captured_at).toLocaleString()}
                    </p>
                    {photo.distance_from_expected !== undefined && (
                      <p className="text-xs">
                        <span className="font-semibold">Distance:</span>{' '}
                        {photo.distance_from_expected.toFixed(0)}m from expected
                      </p>
                    )}
                    <p className="text-xs text-gray-500">
                      {photo.latitude.toFixed(6)}, {photo.longitude.toFixed(6)}
                    </p>
                  </div>
                  <button
                    onClick={() => onPhotoClick && onPhotoClick(photo)}
                    className="mt-2 w-full bg-blue-500 text-white text-xs py-1 px-2 rounded hover:bg-blue-600"
                  >
                    View Details
                  </button>
                </div>
              </Popup>
            </Marker>
          ))}
        </MarkerClusterGroup>
      </MapContainer>

      {/* Legend */}
      <div className="absolute bottom-4 right-4 bg-white p-3 rounded-lg shadow-lg z-[1000]">
        <h4 className="text-xs font-bold mb-2">Legend</h4>
        <div className="space-y-1">
          <div className="flex items-center gap-2">
            <div className="w-4 h-4 rounded-full bg-green-500"></div>
            <span className="text-xs">Verified</span>
          </div>
          <div className="flex items-center gap-2">
            <div className="w-4 h-4 rounded-full bg-yellow-500"></div>
            <span className="text-xs">Flagged</span>
          </div>
          <div className="flex items-center gap-2">
            <div className="w-4 h-4 rounded-full bg-red-500"></div>
            <span className="text-xs">Rejected</span>
          </div>
          <div className="flex items-center gap-2">
            <div className="w-4 h-4 rounded-full border-2 border-blue-500 bg-blue-100"></div>
            <span className="text-xs">Expected Location</span>
          </div>
        </div>
      </div>
    </div>
  );
};

export default PhotoMap;
