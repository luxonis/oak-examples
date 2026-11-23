const $ = (id) => document.getElementById(id);
const canvas = $('preview');
const ctx = canvas.getContext('2d');
let currentState = null;
let candidateKey = '';
let frameSequence = -1;
let pendingImage = 0;

async function command(action, data = {}) {
  try {
    const response = await fetch(`api/${action}`, {method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify(data)});
    const result = await response.json();
    if (!response.ok) throw new Error(result.error);
  } catch (error) {
    $('calibration-message').textContent = error.message;
  }
}
$('calibrate').onclick = () => command('calibrate');

function dimensions(parcel) {
  if (!parcel.dimensions_mm) return parcel.status.replaceAll('_', ' ');
  return parcel.dimensions_mm.map((value) => value === null ? '?' : Math.round(value)).join(' × ') + ' mm';
}

function renderState(state) {
  currentState = state;
  if (state.capture) {
    const source = state.rates?.source_fps;
    const measured = state.rates?.measurement_fps;
    $('stream-profile').textContent = `${state.capture.configured_fps} FPS capture configured · RGB ${state.capture.rgb.join(' × ')} · NeuralDepth ${state.capture.depth.join(' × ')}${source ? ` · source ${source.toFixed(1)} FPS` : ''}${measured ? ` · measurements ${measured.toFixed(1)} FPS` : ''}`;
  }
  const calibration = state.calibration;
  const phase = calibration.phase;
  $('calibration-phase').textContent = {idle: 'Not calibrated', calibrating: 'Finding planes', choosing: 'Choose a plane', ready: 'Calibrated', failed: 'Retry needed'}[phase];
  $('calibration-phase').className = `badge ${phase === 'ready' ? 'ready' : ''}`;
  $('calibrate').disabled = phase === 'calibrating';
  $('calibrate').textContent = phase === 'ready' ? 'Recalibrate support plane' : phase === 'calibrating' ? 'Finding planes…' : 'Find support planes';
  $('calibration-message').textContent = state.error || calibration.message;
  $('selected-plane').hidden = phase !== 'ready';
  if (phase === 'ready') $('selected-plane').textContent = `Using candidate ${calibration.selected + 1}. Camera-to-plane distance ${Math.round(Math.abs(calibration.plane.offset_mm))} mm.`;
  const candidates = calibration.candidates || [];
  const key = `${calibration.generation}-${phase}-${JSON.stringify(candidates.map((candidate) => [candidate.index, candidate.preview?.length]))}`;
  if (key !== candidateKey) {
    candidateKey = key;
    $('candidates').replaceChildren();
    if (phase === 'choosing') for (const candidate of candidates) {
      const card = document.createElement('div'); card.className = 'candidate';
      const title = document.createElement('h3'); title.textContent = `Candidate ${candidate.index + 1}${candidate.recommended ? ' · most support' : ''}`;
      const stats = document.createElement('p'); stats.textContent = `${candidate.inlier_count.toLocaleString()} inliers · ${(candidate.inlier_ratio * 100).toFixed(1)}% of fitted cloud · ${Math.round(Math.abs(candidate.plane.offset_mm))} mm away`;
      card.append(title, stats);
      if (candidate.preview) {const image = document.createElement('img'); image.src = `data:image/jpeg;base64,${candidate.preview}`; image.alt = `Green support plane pixels for candidate ${candidate.index + 1}`; card.append(image);}
      const button = document.createElement('button'); button.textContent = 'Use this support plane'; button.onclick = () => command('select', {generation: calibration.generation, index: candidate.index}); card.append(button);
      $('candidates').append(card);
    }
  }
}

async function renderFrame(frame) {
  if (!frame || frame.sequence === frameSequence) return;
  frameSequence = frame.sequence;
  const token = ++pendingImage;
  const image = new Image(); image.src = `data:image/jpeg;base64,${frame.jpeg}`;
  await image.decode();
  if (token !== pendingImage) return;
  canvas.width = frame.width; canvas.height = frame.height;
  ctx.drawImage(image, 0, 0);
  const labelScale = Math.max(1, canvas.width / 640);
  ctx.font = `bold ${Math.round(13 * labelScale)}px ui-sans-serif, system-ui`;
  for (const parcel of frame.parcels) {
    const [x1, y1, x2, y2] = parcel.bbox;
    const label = `ID ${parcel.track_id} · ${dimensions(parcel)}`;
    const labelWidth = ctx.measureText(label).width + 16 * labelScale;
    const labelX = Math.max(0, Math.min(x1, canvas.width - labelWidth));
    const labelY = y1 >= 27 * labelScale ? y1 - 26 * labelScale : y1;
    ctx.strokeStyle = '#30e0ad'; ctx.lineWidth = 2 * labelScale;
    ctx.strokeRect(x1, y1, x2 - x1, y2 - y1);
    ctx.fillStyle = '#183d35'; ctx.fillRect(labelX, labelY, labelWidth, 25 * labelScale);
    ctx.fillStyle = '#d7fff0'; ctx.fillText(label, labelX + 8 * labelScale, labelY + 17 * labelScale);
  }
  $('empty').style.display = 'none';
  $('frame-number').textContent = `Frame ${frame.sequence}`;
  $('frame-status').textContent = frame.message;
  $('parcels').replaceChildren();
  for (const parcel of frame.parcels) {
    const card = document.createElement('div'); card.className = 'parcel';
    const title = document.createElement('strong'); title.textContent = `Parcel ID ${parcel.track_id}`;
    const measurement = document.createElement('span'); measurement.textContent = dimensions(parcel);
    const status = document.createElement('small'); status.textContent = parcel.status.replaceAll('_', ' ');
    card.append(title, measurement, status); $('parcels').append(card);
  }
}

function connect() {
  const url = new URL('ws', location.href); url.protocol = location.protocol === 'https:' ? 'wss:' : 'ws:';
  const socket = new WebSocket(url);
  socket.onopen = () => {$('connection').textContent = 'Camera connected'; $('connection').className = 'badge ready';};
  socket.onmessage = ({data}) => {const snapshot = JSON.parse(data); renderState(snapshot.state); renderFrame(snapshot.frame).catch(console.error);};
  socket.onclose = () => {$('connection').textContent = 'Reconnecting'; $('connection').className = 'badge offline'; setTimeout(connect, 1500);};
  socket.onerror = () => socket.close();
}
connect();
