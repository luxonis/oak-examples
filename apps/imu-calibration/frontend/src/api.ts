import type { DAIConnection, DAIService } from '@luxonis/depthai-viewer-common';

export type Matrix = number[][];
export type Vec3 = [number, number, number];

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

export type CalibrationStatus = 'missing' | 'default' | 'calibrated';

export interface CalibrationResult {
	rotation: Matrix;
	accelerometer: Matrix;
	gyroscope: Matrix;
	poseErrors: number[];
	problems: string[];
	specMatch: boolean | null;
	flashed: boolean;
}

export interface ImuState {
	/** Changes when the backend restarts. */
	session: number;
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
	device: DeviceInfo;
	result: CalibrationResult | null;
}

/** RAW sample in the sensor-native frame. */
export interface Sample {
	seq: number;
	accel: Vec3;
	gyro: Vec3;
	mag: Vec3;
}

export type Action = 'capture' | 'back' | 'redo' | 'flash';

const SERVICES = ['IMU State', 'IMU Action'] as const;
type Service = (typeof SERVICES)[number];
// Custom services are not part of the DAIService enum.
export const ACTIVE_SERVICES = SERVICES as unknown as DAIService[];

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
