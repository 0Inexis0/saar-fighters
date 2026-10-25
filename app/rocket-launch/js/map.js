import {state, baseSite, MAP_DIMENSIONS, targetDestruction, targetMarker, targetCoords, targetRange, targetETA} from './missile.js';
import {formatCoordinate, formatEta, haversineKm, writeLog} from './ui.js';

const qs = (sel) => document.querySelector(sel);
export const trajectoryLine = qs("#trajectoryLine");
export const launchSite = qs("#launchSite");
export const mapOverlay = qs("#mapOverlay");

export const strategicTargets = [
  {id: "europe", label: "EUROPE NODE", lat: 52.52, lon: 13.405},
  {id: "africa", label: "AFRICA GRID", lat: 30.0444, lon: 31.2357},
  {id: "middle-east", label: "M.E. RELAY", lat: 24.7136, lon: 46.6753},
  {id: "asia", label: "ASIA COMMAND", lat: 35.6895, lon: 139.6917},
  {id: "south-america", label: "S. AMERICA HUB", lat: -23.5505, lon: -46.6333},
  {id: "australia", label: "PACIFIC WATCH", lat: -33.8688, lon: 151.2093},
];

export function latLonToFraction(lat, lon) {
  return {x: (lon + 180) / 360, y: (90 - lat) / 180};
}

export function latLonToSvg(lat, lon) {
  const fraction = latLonToFraction(lat, lon);
  return {x: fraction.x * MAP_DIMENSIONS.width, y: fraction.y * MAP_DIMENSIONS.height};
}

export function positionElementAtLatLon(el, lat, lon) {
  if (!el) return;
  const {x, y} = latLonToFraction(lat, lon);
  el.style.left = `${(x * 100).toFixed(2)}%`;
  el.style.top = `${(y * 100).toFixed(2)}%`;
  el.style.right = "auto";
  el.style.bottom = "auto";
}

export function buildArcPath(start, end) {
  const dx = Math.abs(end.x - start.x);
  const curve = Math.max(60, dx * 0.18);
  const controlX = (start.x + end.x) / 2;
  const controlY = Math.max(30, Math.min(start.y, end.y) - curve);
  return `M${start.x.toFixed(1)} ${start.y.toFixed(1)} Q${controlX.toFixed(1)} ${controlY.toFixed(1)} ${end.x.toFixed(1)} ${end.y.toFixed(1)}`;
}

export function renderTargetOverlay(activeId) {
  if (!mapOverlay) return;

  const basePoint = latLonToSvg(baseSite.lat, baseSite.lon);
  const fragments = [];
  const destroyedId = state.mapData.destroyedTargetId;
  const isLaunchPhase = state.phase === "launched";
  const showCrosshairPhase = state.phase === "armed" || state.phase === "counting";

  strategicTargets.forEach((target) => {
    const targetPoint = latLonToSvg(target.lat, target.lon);
    const arcPath = buildArcPath(basePoint, targetPoint);

    const isPrimaryTarget = activeId === target.id && state.mapData.hasTarget && !state.targetDestroyed;
    const isDestroyedTarget = destroyedId === "all" || destroyedId === target.id;
    const highlightArc = isLaunchPhase || showCrosshairPhase || isPrimaryTarget || isDestroyedTarget;

    const crosshairRadius = isDestroyedTarget ? 18 : isPrimaryTarget ? 16 : 14;
    const crosshairSpan = isDestroyedTarget ? 15 : isPrimaryTarget ? 13 : 11;
    const crosshairClasses = ["target-crosshair"];

    if (showCrosshairPhase) crosshairClasses.push("prelaunch");
    if (isLaunchPhase) crosshairClasses.push("launch");
    if (isPrimaryTarget) crosshairClasses.push("active");
    if (isDestroyedTarget) crosshairClasses.push("destroyed");

    const crosshairMarkup = `<g class="${crosshairClasses.join(" ")}">
          <circle class="crosshair-ring" r="${crosshairRadius}"></circle>
          <line class="crosshair-line" x1="${-crosshairSpan}" y1="0" x2="${crosshairSpan}" y2="0"></line>
          <line class="crosshair-line" x1="0" y1="${-crosshairSpan}" x2="0" y2="${crosshairSpan}"></line>
        </g>`;

    const explosionMarkup = isDestroyedTarget
      ? `<g class="detonation-marker">
          <g class="detonation-flash">
            <circle class="detonation-ring shock" r="26"></circle>
            <circle class="detonation-ring wave" r="16"></circle>
            <circle class="detonation-core" r="7"></circle>
          </g>
          <g class="detonation-residue">
            <circle class="detonation-residue-core" r="5"></circle>
            <circle class="detonation-residue-ring" r="11"></circle>
            <circle class="detonation-residue-ring outer" r="18"></circle>
            <line class="detonation-residue-mark" x1="-8" y1="0" x2="8" y2="0"></line>
            <line class="detonation-residue-mark" x1="0" y1="-8" x2="0" y2="8"></line>
          </g>
        </g>`
      : "";

    const shouldShowTrajectory = highlightArc || (state.multiTargetStrike && isLaunchPhase);
    fragments.push(
      `<path class="trajectory-arc${shouldShowTrajectory ? " active" : ""}" d="${arcPath}"></path>`
    );

    const shouldShowFlightDot = state.phase === "launched" && !state.targetDestroyed && (state.multiTargetStrike || isPrimaryTarget);
    if (shouldShowFlightDot) {
      fragments.push(`
        <circle class="flight-dot" r="3.2">
          <animateMotion
            dur="${state.flightDurationSec}s"
            repeatCount="1"
            fill="freeze"
            begin="0s"
            keySplines="0.3 0 0.2 1"
            keyTimes="0;1"
            calcMode="spline"
            path="${arcPath}" />
        </circle>`);
    }

    const nodeClasses = ["target-node"];
    if (isPrimaryTarget) nodeClasses.push("active");
    if (isDestroyedTarget) nodeClasses.push("detonated");

    fragments.push(
      `<g class="${nodeClasses.join(" ")}" transform="translate(${targetPoint.x.toFixed(1)} ${targetPoint.y.toFixed(1)})">
        <circle class="target-glow" r="${isPrimaryTarget ? 11 : 8}"></circle>
        <circle class="target-dot" r="${isPrimaryTarget ? 5.5 : 4}"></circle>
        ${explosionMarkup}
        ${crosshairMarkup}
        <text class="target-label" x="10" y="-10">${target.label}</text>
      </g>`
    );
  });

  mapOverlay.innerHTML = fragments.join("");
  if (state.phase === "launched" && !state.targetDestroyed) {
    const flightDots = mapOverlay.querySelectorAll(".flight-dot animateMotion");
    flightDots.forEach(dot => dot.beginElement());
  }
}

export function updateWorldMap() {
  positionElementAtLatLon(launchSite, baseSite.lat, baseSite.lon);
  const activeArcId = state.mapData.hasTarget && !state.targetDestroyed && !state.multiTargetStrike ? state.mapData.targetId : null;
  renderTargetOverlay(activeArcId);

  if (state.mapData.hasTarget) {
    if (state.multiTargetStrike) {
      targetDestruction.style.display = "none";
      targetMarker.style.display = "none";
      if (trajectoryLine) trajectoryLine.style.display = "none";

      targetCoords.textContent = "MULTI-LOCK // GLOBAL";
      targetRange.textContent = `${strategicTargets.length} Ziele`;
      targetETA.textContent = "--:--";
      return;
    }
    const {lat, lon} = state.mapData.targetCoords;
    positionElementAtLatLon(targetDestruction, lat, lon);

    if (!state.targetDestroyed) {
      targetDestruction.style.display = "none";
    }
    targetMarker.style.display = "none";
    if (trajectoryLine) trajectoryLine.style.display = "none";
    targetCoords.textContent = `${formatCoordinate(lat, "lat")}, ${formatCoordinate(lon, "lon")}`;
    targetRange.textContent = `${state.mapData.range} km`;
    targetETA.textContent = formatEta(state.mapData.eta);
  } else {
    targetMarker.style.display = "none";
    targetDestruction.style.display = "none";
    if (trajectoryLine) trajectoryLine.style.display = "none";
    targetCoords.textContent = "--°N, --°E";
    targetRange.textContent = "-- km";
    targetETA.textContent = "--:--";
  }
}

export function setRandomTarget() {
  const candidates = strategicTargets.filter((target) => target.id !== state.mapData.targetId);
  const selection = candidates.length ? candidates : strategicTargets;
  const target = selection[Math.floor(Math.random() * selection.length)];
  const distance = haversineKm(baseSite.lat, baseSite.lon, target.lat, target.lon);
  const etaSeconds = state.flightDurationSec;
  state.mapData = {
    targetId: target.id,
    destroyedTargetId: null,
    targetLabel: "GLOBAL STRIKE",
    targetCoords: {lat: target.lat, lon: target.lon},
    range: distance,
    eta: etaSeconds,
    hasTarget: true,
  };
  state.targetDestroyed = false;
  state.mapData.destroyedTargetId = null;
  state.multiTargetStrike = true;
  targetDestruction.style.display = "none";
  updateWorldMap();
  const strikeCount = strategicTargets.length;
  writeLog(`${strikeCount} Ziele erfasst`);
}

export function clearTarget() {
  state.mapData.hasTarget = false;
  state.mapData.targetId = null;
  state.mapData.targetLabel = "";
  state.mapData.destroyedTargetId = null;
  state.targetDestroyed = false;
  state.multiTargetStrike = false;
  targetMarker.style.display = "none";
  targetDestruction.style.display = "none";
  updateWorldMap();
  writeLog("Ziel entfernt");
}
