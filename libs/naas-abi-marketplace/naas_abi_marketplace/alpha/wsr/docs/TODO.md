# WSR — TODO

## In progress

- [ ] Fix Reuters RSS feed (blocked/paywalled, replace with AP News or DW)

## Backlog

### Street view
- [ ] Integrate Mapillary street-level imagery on globe click
  - Right-click / long-press on any globe point queries `graph.mapillary.com/images?bbox=...`
  - Slide-in panel renders `@mapillary/mapillary-js` 360 viewer (MIT)
  - Falls back to "No imagery available" when coverage is absent
  - Requires free Mapillary access token (mapillary.com/developer)

### Data feeds
- [ ] Add OpenSky OAuth2 credentials for full flight data (post-March 2025 accounts)
- [ ] Add TfL app key for higher rate limit on London CCTV (~900 cameras)
- [ ] Add OpenWebcamDB key to enable global webcam layer
- [ ] Evaluate adding AP News / DW / France24 RSS alongside BBC and Al Jazeera

### Globe / UX
- [ ] Add Cesium Ion token for satellite terrain and ESRI satellite imagery (free at ion.cesium.com)
- [ ] Persist globe camera position across reloads (localStorage)
- [ ] Add time scrubber — replay last 24h of flight/seismic data
- [ ] Mobile responsiveness pass (panels, status bar, intel ticker)

### Auth
- [ ] Move credentials to backend (currently client-side sessionStorage)
- [ ] Support multiple operator accounts with roles
- [ ] Add session expiry / inactivity timeout

### Deployment
- [ ] Dockerise both `apps/api` and `apps/web` with a single `docker compose up`
- [ ] Add `apps/api` to the ABI Docker Compose stack as a named service
- [ ] Expose WSR globe as an embedded panel inside Nexus (iFrame or micro-frontend)
- [ ] Wire WSR API URL into `config.local.yaml` so secrets and port are config-driven

### Agent
- [ ] Give WSRAgent live tool access to the API endpoints (flights, earthquakes, news)
- [ ] Add intent: "Show me what is happening near [location]" with Mapillary + OSINT lookup
- [ ] Register WSRAgent in Nexus chat so users can ask situational questions from the main UI
