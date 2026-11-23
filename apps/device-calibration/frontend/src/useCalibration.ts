import { useDaiConnection } from '@luxonis/depthai-viewer-common';
import { useEffect, useRef, useState } from 'react';
import {
	type Act,
	type CalibrationState,
	type Sample,
	callService,
} from './api.ts';

export const WINDOW = 250; // IMU graph samples (10 s at 25 Hz), matches the backend buffer
const POLL_MS = 100;

// `?mock=<name>` renders fixtures/<name>.json instead of a live backend (screenshots, layout work).
const FIXTURES = import.meta.glob<CalibrationState>('./fixtures/*.json', {
	import: 'default',
});
const MOCK = new URLSearchParams(window.location.search).get('mock');

export function useCalibration() {
	const { connected, daiConnection } = useDaiConnection();
	const [state, setState] = useState<CalibrationState | null>(null);
	const [rows, setRows] = useState<Sample[]>([]);
	const since = useRef(0);
	const session = useRef<number | null>(null);

	useEffect(() => {
		if (!MOCK) return;
		const load = FIXTURES[`./fixtures/${MOCK}.json`];
		void load?.().then((s) => {
			setState(s);
			setRows(s.imu?.samples ?? []);
		});
	}, []);

	useEffect(() => {
		if (MOCK || !connected) return;
		const id = window.setInterval(() => {
			callService<CalibrationState>(
				daiConnection,
				'Calibration State',
				{ since: since.current },
				(s) => {
					const restarted = s.session !== session.current;
					session.current = s.session;
					const samples = s.imu?.samples ?? [];
					since.current = restarted
						? 0
						: Math.max(since.current, s.imu?.seq ?? 0);
					// Replies can arrive out of order, so keep only samples newer than the buffer.
					setRows((prev) => {
						const kept = restarted ? [] : prev;
						const last = kept.at(-1)?.seq ?? 0;
						return [...kept, ...samples.filter((r) => r.seq > last)].slice(
							-WINDOW,
						);
					});
					setState(s);
				},
			);
		}, POLL_MS);
		return () => window.clearInterval(id);
	}, [connected, daiConnection]);

	const act: Act = (action, body = {}) =>
		callService(daiConnection, 'Calibration Action', { action, ...body });

	return { state, rows, act, connected: connected || MOCK !== null };
}
