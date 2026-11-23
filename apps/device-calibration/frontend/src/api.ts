import type { DAIConnection, DAIService } from '@luxonis/depthai-viewer-common';

export type Matrix = number[][];
export type Vec3 = [number, number, number];

// ---- Device and stored IMU calibration (left sidebar) ----

export type CalibrationStatus = 'missing' | 'default' | 'calibrated';

export interface StoredCalibration {
	rotation: Matrix | null;
	accelerometer: Matrix | null;
	gyroscope: Matrix | null;
}

export interface DeviceInfo {
	name: string;
	id: string;
	platform: string;
	productName: string;
	boardName: string;
	boardRev: string;
	imu: string;
	imuFirmware: string;
	magnetometer: boolean;
	extrinsics: 'flashed' | 'missing';
	accelerometer: CalibrationStatus;
	gyroscope: CalibrationStatus;
	socket: string;
	translationCm: number[];
	mountingSource: string;
	calibration: StoredCalibration;
}

// ---- Setup: board config and ChArUco spec ----

export interface Charuco {
	squaresX: number;
	squaresY: number;
	squareCm: number;
	markerCm: number;
	dictionary: string;
}

export interface BoardCamera {
	name: string;
	type: 'color' | 'mono' | 'tof' | 'thermal';
	hfov: number;
	extrinsics?: {
		to_cam: string;
		specTranslation: { x: number; y: number; z: number };
		rotation: { r: number; p: number; y: number };
	};
	enabled: boolean;
	connected: boolean;
	model: 'perspective' | 'fisheye';
	sensorName: string;
	size: [number, number];
	hasAutofocus: boolean;
	lensPosition: number;
}

export interface BoardConfig {
	name: string;
	revision?: string;
	/** Keyed by socket, e.g. "CAM_A". */
	cameras: Record<string, BoardCamera>;
	stereo_config?: { left_cam: string; right_cam: string };
}

// ---- Capture ----

export type PoseBucket = 'frontal' | 'left' | 'right' | 'up' | 'down';

export interface PairState {
	key: string;
	a: string;
	b: string;
	shared: number;
	need: number;
	coverageA: number;
	coverageB: number;
	ok: boolean;
}

export interface CaptureState {
	sets: number;
	auto: boolean;
	ready: boolean;
	canProcess: boolean;
	saving: boolean;
	grid: number;
	guidance: { text: string; camera: string | null };
	cameras: Record<
		string,
		{ coverage: number; detected: boolean; sets: number }
	>;
	pairs: PairState[];
	/** Selected pair key for the pair view, or null for the camera view. */
	view: string | null;
	poses: Record<PoseBucket, { have: number; need: number }>;
}

// ---- Camera results ----

export interface CameraResult {
	cameras: {
		socket: string;
		name: string;
		model: string;
		size: [number, number];
		views: number;
		coverage: number;
		rmsNew: number;
		rmsOld: number | null;
	}[];
	pairs: {
		from: string;
		to: string;
		views: number;
		newPx: number;
		oldPx: number | null;
	}[];
	stereo: {
		left: string;
		right: string;
		epipolarNew: number;
		epipolarOld: number | null;
	} | null;
	problems: string[];
	warnings: string[];
}

// ---- IMU ----

/** RAW sample in the sensor-native frame. */
export interface Sample {
	seq: number;
	accel: Vec3;
	gyro: Vec3;
	mag: Vec3;
}

export interface ImuResult {
	rotation: Matrix;
	accelerometer: Matrix;
	gyroscope: Matrix;
	/** Per-pose angle (deg) between the measured gravity and the guide. */
	poseTilts: number[];
	problems: string[];
	specMatch: boolean | null;
	flashed: boolean;
}

export interface ImuState {
	seq: number;
	phase: 'pose' | 'capturing' | 'results';
	pose: { index: number; count: number; instruction: string };
	progress: number;
	imuReady: boolean;
	still: boolean;
	orientationError: string | null;
	message: string;
	messageOk: boolean;
	samples: Sample[];
	result: ImuResult | null;
}

export interface ImuMounting {
	source: 'board' | 'six-pose';
	reason: string;
	sets: number;
	spreadDeg: number | null;
	residualDeg: number | null;
	specErrorRpyDeg: [number, number, number] | null;
	specErrorDeg: number | null;
}

// ---- Whole app state ----

export type Phase =
	| 'setup'
	| 'capture'
	| 'processing'
	| 'results'
	| 'imu'
	| 'review';

export interface CalibrationState {
	/** Changes when the backend restarts. */
	session: number;
	phase: Phase;
	message: string;
	messageOk: boolean;
	device: DeviceInfo;
	boardNames: string[];
	boardSource: string;
	board: BoardConfig;
	boardProblems: string[];
	dictionaries: string[];
	lastCharuco: Charuco | null;
	charuco: Charuco | null;
	boardFixed: boolean;
	capture: CaptureState | null;
	processing: { progress: number; stage: string } | null;
	cameraResult: CameraResult | null;
	imu: ImuState | null;
	imuMounting: ImuMounting | null;
	/** Everything that blocks Flash (camera + IMU + mounting). */
	problems: string[];
	dryRun: boolean;
	flashed: boolean;
	backupPath: string | null;
}

/** Sends a `Calibration Action`; `body` carries the action's arguments. */
export type Act = (action: string, body?: Record<string, unknown>) => void;

/** Props every step's `Main` and `Side` component receives. */
export interface StepProps {
	state: CalibrationState;
	rows: Sample[];
	act: Act;
}

export type Service =
	| 'Calibration State'
	| 'Calibration Action'
	| 'Board Preview';

export function callService<T>(
	connection: DAIConnection | null,
	service: Service,
	body: Record<string, unknown>,
	onResponse: (response: T) => void = () => {},
) {
	void connection?.postToService(
		service as unknown as DAIService,
		body,
		(response) => onResponse(decode(response) as T),
	);
}

function decode(response: unknown): unknown {
	let payload = (response as { data?: unknown })?.data ?? response;
	if (ArrayBuffer.isView(payload) || payload instanceof ArrayBuffer) {
		payload = new TextDecoder().decode(payload);
	}
	return typeof payload === 'string' ? JSON.parse(payload) : payload;
}

/** DepthAI applies stored IMU calibration as Q @ (R @ raw) + b; a missing part acts as identity. */
export function applyCalibration(
	rotation: Matrix | null,
	qb: Matrix | null,
	v: Vec3,
): Vec3 {
	const r = rotation ? (rotation.map((row) => dot(row, v)) as Vec3) : v;
	return qb ? (qb.map((row) => dot(row, r) + row[3]) as Vec3) : r;
}

function dot(row: number[], v: Vec3): number {
	return row[0] * v[0] + row[1] * v[1] + row[2] * v[2];
}

export function meanVec(values: Vec3[]): Vec3 | null {
	if (!values.length) return null;
	const sum = values.reduce<Vec3>(
		(acc, v) => [acc[0] + v[0], acc[1] + v[1], acc[2] + v[2]],
		[0, 0, 0],
	);
	return [
		sum[0] / values.length,
		sum[1] / values.length,
		sum[2] / values.length,
	];
}

export const norm = (v: Vec3) => Math.hypot(v[0], v[1], v[2]);
