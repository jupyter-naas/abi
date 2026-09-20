'use client';

import { useEffect, useState } from 'react';
import {
  Camera,
  ExternalLink,
  Globe,
  Navigation,
  Phone,
  Search,
} from 'lucide-react';
import type { MapsPinMarker } from '../lib/leaflet-map';
import { resolvePinMedia } from '../lib/maps-pin-media';

type CardPhoto = { url: string; label?: string; source: string };
type PlaceCard = {
  source: string;
  rating?: number;
  reviewCount?: number;
  category?: string;
  website?: string;
  phone?: string;
  address?: string;
  photos?: CardPhoto[];
};

function fallbackPhotos(media: ReturnType<typeof resolvePinMedia>): CardPhoto[] {
  const photos: CardPhoto[] = [];
  if (media.photoUrl) photos.push({ url: media.photoUrl, label: 'Cited', source: 'cited' });
  photos.push({ url: media.previewUrl, label: 'Street View', source: 'streetview' });
  return photos;
}

export function MapsRecordMedia({ pin }: { pin: MapsPinMarker }) {
  const media = resolvePinMedia(pin);
  const [card, setCard] = useState<PlaceCard | null>(null);

  useEffect(() => {
    const controller = new AbortController();
    fetch(media.placeCardUrl, { signal: controller.signal })
      .then((res) => (res.ok ? res.json() : null))
      .then((data: PlaceCard | null) => {
        if (data) setCard(data);
      })
      .catch(() => undefined);
    return () => controller.abort();
  }, [media.placeCardUrl]);

  const photos = card?.photos?.length ? card.photos : fallbackPhotos(media);
  const website = card?.website ?? media.websiteUrl;
  const phone = card?.phone ?? media.phone;
  const address = card?.address ?? pin.address ?? pin.detail?.split('\n')[0];
  const category = card?.category ? `${card.category} · ${pin.country || pin.label}` : media.category;
  const rating = card?.rating;
  const reviews = card?.reviewCount;

  return (
    <div className="maps-record-media maps-record-card">
      <div
        className={
          'maps-record-photos' + (photos.length === 1 ? ' maps-record-photos--one' : '')
        }
      >
        {photos.slice(0, 2).map((photo, index) => (
          <a
            key={photo.url + index}
            href={index === 0 ? media.imageSearchUrl : media.streetViewUrl}
            target="_blank"
            rel="noreferrer"
            className="maps-record-photos__item"
          >
            <img src={photo.url} alt="" referrerPolicy="no-referrer" />
            {index === 0 ? (
              <span className="maps-record-photos__see">See photos</span>
            ) : photo.label ? (
              <span className="maps-record-photos__label">{photo.label}</span>
            ) : null}
          </a>
        ))}
      </div>
      <h2>{media.title}</h2>
      {typeof rating === 'number' && (
        <p className="maps-record-card__rating">
          {rating.toFixed(1)}
          {typeof reviews === 'number' ? ` · ${reviews} reviews` : ''}
        </p>
      )}
      {category && <p className="maps-record-card__meta">{category}</p>}
      <div className="maps-record-chips">
        {website && (
          <a className="maps-record-chip" href={website} target="_blank" rel="noreferrer">
            <Globe size={14} /> Website
          </a>
        )}
        <a className="maps-record-chip" href={media.directionsUrl} target="_blank" rel="noreferrer">
          <Navigation size={14} /> Directions
        </a>
        <a
          className="maps-record-chip maps-record-streetview"
          href={media.streetViewUrl}
          target="_blank"
          rel="noreferrer"
        >
          <Camera size={14} /> Street View
        </a>
        <a
          className="maps-record-chip maps-record-images"
          href={media.imageSearchUrl}
          target="_blank"
          rel="noreferrer"
        >
          <Search size={14} /> Search images
        </a>
        {phone && (
          <a className="maps-record-chip" href={`tel:${phone.replace(/[^\d+]/g, '')}`}>
            <Phone size={14} /> Call
          </a>
        )}
      </div>
      {address && (
        <p className="maps-record-fact">
          <span>Address</span> {address}
        </p>
      )}
      {phone && (
        <p className="maps-record-fact">
          <span>Phone</span> {phone}
        </p>
      )}
      {media.photoSource && (
        <p className="maps-record-fact">
          <a href={media.photoSource} target="_blank" rel="noreferrer">
            Cited photo source <ExternalLink size={12} />
          </a>
        </p>
      )}
    </div>
  );
}
