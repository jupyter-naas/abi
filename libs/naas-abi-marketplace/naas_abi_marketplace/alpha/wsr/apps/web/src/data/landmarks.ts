import type { City } from '@/lib/types';

export const CITIES: Record<string, City> = {
  'global': {
    name: 'Global Overview',
    landmarks: [
      { key: 'q', name: 'Earth Overview',    lat: 20,  lon: 0,    alt: 20000000, heading: 0, pitch: -90 },
      { key: 'w', name: 'North America',     lat: 45,  lon: -100, alt: 10000000, heading: 0, pitch: -70 },
      { key: 'e', name: 'Europe',            lat: 50,  lon: 10,   alt: 7000000,  heading: 0, pitch: -70 },
      { key: 'r', name: 'Asia Pacific',      lat: 20,  lon: 105,  alt: 10000000, heading: 0, pitch: -70 },
      { key: 't', name: 'Middle East',       lat: 25,  lon: 45,   alt: 5000000,  heading: 0, pitch: -70 },
    ],
  },
  'usa': {
    name: 'United States',
    landmarks: [
      { key: 'q', name: 'Continental US',   lat: 39.5, lon: -98.5, alt: 5500000, heading: 0,   pitch: -75 },
      { key: 'w', name: 'East Coast',       lat: 38,   lon: -77,   alt: 2500000, heading: 0,   pitch: -70 },
      { key: 'e', name: 'West Coast',       lat: 37,   lon: -120,  alt: 2200000, heading: 0,   pitch: -70 },
      { key: 'r', name: 'Gulf Coast',       lat: 29,   lon: -90,   alt: 2000000, heading: 0,   pitch: -70 },
      { key: 't', name: 'NYC Metro Area',   lat: 40.7, lon: -74,   alt: 350000,  heading: 0,   pitch: -60 },
    ],
  },
  'new-york': {
    name: 'New York City',
    landmarks: [
      { key: 'q', name: 'Manhattan Overview', lat: 40.745, lon: -73.987, alt: 18000,  heading: 0,   pitch: -55 },
      { key: 'w', name: 'Times Square',       lat: 40.758, lon: -73.985, alt: 500,    heading: 180, pitch: -20 },
      { key: 'e', name: 'Central Park',       lat: 40.785, lon: -73.968, alt: 2500,   heading: 0,   pitch: -50 },
      { key: 'r', name: '5th Ave & 42nd St',  lat: 40.752, lon: -73.982, alt: 180,    heading: 160, pitch: -12 },
      { key: 't', name: 'Brooklyn Bridge',    lat: 40.706, lon: -73.997, alt: 400,    heading: 270, pitch: -20 },
    ],
  },
  'london': {
    name: 'London',
    landmarks: [
      { key: 'q', name: 'London Overview',   lat: 51.505, lon: -0.09,  alt: 15000,  heading: 0,   pitch: -55 },
      { key: 'w', name: 'Big Ben',           lat: 51.500, lon: -0.124, alt: 600,    heading: 90,  pitch: -25 },
      { key: 'e', name: 'Buckingham Palace', lat: 51.501, lon: -0.141, alt: 500,    heading: 180, pitch: -25 },
      { key: 'r', name: 'Tower Bridge St',   lat: 51.505, lon: -0.075, alt: 180,    heading: 0,   pitch: -10 },
      { key: 't', name: 'Canary Wharf',      lat: 51.505, lon: -0.023, alt: 800,    heading: 45,  pitch: -30 },
    ],
  },
  'dubai': {
    name: 'Dubai',
    landmarks: [
      { key: 'q', name: 'Dubai Overview',   lat: 25.13,  lon: 55.22,  alt: 25000,  heading: 0,   pitch: -55 },
      { key: 'w', name: 'Burj Khalifa',     lat: 25.197, lon: 55.274, alt: 1200,   heading: 0,   pitch: -20 },
      { key: 'e', name: 'Palm Jumeirah',    lat: 25.112, lon: 55.139, alt: 3000,   heading: 0,   pitch: -60 },
      { key: 'r', name: 'Sheikh Zayed Rd',  lat: 25.185, lon: 55.255, alt: 200,    heading: 0,   pitch: -12 },
      { key: 't', name: 'Dubai Airport',    lat: 25.253, lon: 55.365, alt: 2000,   heading: 90,  pitch: -40 },
    ],
  },
  'tokyo': {
    name: 'Tokyo',
    landmarks: [
      { key: 'q', name: 'Tokyo Overview',   lat: 35.68,  lon: 139.74, alt: 18000,  heading: 0,   pitch: -55 },
      { key: 'w', name: 'Shibuya Crossing', lat: 35.659, lon: 139.700, alt: 200,   heading: 180, pitch: -15 },
      { key: 'e', name: 'Imperial Palace',  lat: 35.685, lon: 139.752, alt: 800,   heading: 90,  pitch: -30 },
      { key: 'r', name: 'Shinjuku St',      lat: 35.690, lon: 139.699, alt: 180,   heading: 45,  pitch: -12 },
      { key: 't', name: 'Mount Fuji',       lat: 35.360, lon: 138.727, alt: 8000,  heading: 0,   pitch: -15 },
    ],
  },
  'pentagon': {
    name: 'Pentagon / DC',
    landmarks: [
      { key: 'q', name: 'Pentagon',         lat: 38.871, lon: -77.056, alt: 1000,  heading: 0,   pitch: -60 },
      { key: 'w', name: 'White House St',   lat: 38.897, lon: -77.036, alt: 180,   heading: 180, pitch: -12 },
      { key: 'e', name: 'Capitol Building', lat: 38.889, lon: -77.009, alt: 600,   heading: 270, pitch: -25 },
      { key: 'r', name: 'NSA Fort Meade',   lat: 39.108, lon: -76.771, alt: 2000,  heading: 0,   pitch: -45 },
      { key: 't', name: 'Langley CIA',      lat: 38.951, lon: -77.145, alt: 1500,  heading: 90,  pitch: -40 },
    ],
  },
};

export const CITY_KEYS = ['global', 'usa', 'new-york', 'london', 'dubai', 'tokyo', 'pentagon'];
