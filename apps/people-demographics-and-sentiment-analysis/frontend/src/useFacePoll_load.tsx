import { useDaiConnection } from '@luxonis/depthai-viewer-common';
import { useEffect, useRef, useState } from 'react';
import { postToPeopleAnalyticsService } from './services.ts';

export type EmotionName =
	| 'Happiness'
	| 'Anger'
	| 'Neutral'
	| 'Sadness'
	| 'Surprise'
	| 'Fear'
	| 'Disgust'
	| 'Contempt';

export type FaceMeta = {
	id?: string;
	status?: 'NEW' | 'REID' | 'TBD';
	age?: number;
	gender?: 'Male' | 'Female';
	emotion?: EmotionName;
	img_url?: string;
};

export type FaceStats = {
	age: number;
	males: number;
	females: number;
	emotions: Partial<Record<EmotionName, number>>;
};

type FacesPayload = {
	faces?: FaceMeta[];
	stats?: FaceStats;
};

function decodePayload(response: unknown): unknown {
	let payload = response;

	if (
		typeof payload === 'object' &&
		payload !== null &&
		Object.hasOwn(payload, 'data')
	) {
		payload = (payload as { data: unknown }).data;
	}

	if (typeof payload === 'string') {
		return JSON.parse(payload);
	}

	if (payload instanceof DataView) {
		return JSON.parse(new TextDecoder().decode(payload));
	}

	if (payload instanceof ArrayBuffer) {
		return JSON.parse(new TextDecoder('utf-8').decode(payload));
	}

	if (ArrayBuffer.isView(payload)) {
		return JSON.parse(
			new TextDecoder('utf-8').decode(
				new Uint8Array(payload.buffer, payload.byteOffset, payload.byteLength),
			),
		);
	}

	return payload;
}

function parseFacesPayload(response: unknown): FacesPayload | null {
	try {
		const payload = decodePayload(response);
		return typeof payload === 'object' && payload !== null
			? (payload as FacesPayload)
			: null;
	} catch (error) {
		console.error('[PeopleAnalytics] Failed to parse faces payload:', error);
		return null;
	}
}

function shallowEqualFaces(
	a: (FaceMeta | undefined)[],
	b: (FaceMeta | undefined)[],
) {
	if (a.length !== b.length) return false;

	for (let i = 0; i < a.length; i++) {
		const left = a[i];
		const right = b[i];

		if (!left && !right) continue;
		if (!left || !right) return false;

		if (
			left.id !== right.id ||
			left.age !== right.age ||
			left.gender !== right.gender ||
			left.emotion !== right.emotion ||
			left.img_url !== right.img_url
		) {
			return false;
		}
	}

	return true;
}

export function useFacesPoll() {
	const { connected, daiConnection } = useDaiConnection();
	const [faces, setFaces] = useState<(FaceMeta | undefined)[]>([
		undefined,
		undefined,
		undefined,
	]);
	const [stats, setStats] = useState<FaceStats | undefined>(undefined);
	const inFlight = useRef(false);
	const timer = useRef<number | null>(null);

	useEffect(() => {
		if (!connected) return;

		const tick = () => {
			if (inFlight.current || document.hidden) return;
			inFlight.current = true;

			postToPeopleAnalyticsService(
				daiConnection,
				'Get Faces',
				{},
				(response) => {
					const payload = parseFacesPayload(response);
					const payloadFaces = Array.isArray(payload?.faces)
						? payload.faces
						: [];
					const next: (FaceMeta | undefined)[] = [
						payloadFaces[0],
						payloadFaces[1],
						payloadFaces[2],
					];

					setFaces((previous) =>
						shallowEqualFaces(previous, next) ? previous : next,
					);

					if (payload?.stats) {
						setStats(payload.stats);
					}

					inFlight.current = false;
				},
			);
		};

		const loop = () => {
			tick();
			timer.current = window.setTimeout(loop, 1000);
		};

		loop();
		return () => {
			if (timer.current) window.clearTimeout(timer.current);
			inFlight.current = false;
		};
	}, [connected, daiConnection]);

	return { faces, stats };
}
