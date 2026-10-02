import { useDaiConnection } from '@luxonis/depthai-viewer-common';
import type { RefObject } from 'react';
import { useEffect } from 'react';
import {
	type P2PMeasurementService,
	postToP2PMeasurementService,
} from './services.ts';

const clamp = (value: number) => Math.max(0, Math.min(1, value));

function parseResponse(response: unknown): {
	ok?: boolean;
	point_count?: number;
} {
	try {
		if (response instanceof DataView) {
			return JSON.parse(new TextDecoder().decode(response));
		}

		if (typeof response === 'string') {
			return JSON.parse(response);
		}

		return typeof response === 'object' && response !== null
			? (response as { ok?: boolean; point_count?: number })
			: { ok: true };
	} catch {
		return { ok: true };
	}
}

export function ClickCatcher({
	containerRef,
	frameWidth = 640,
	frameHeight = 400,
	serviceName = 'Selection Service',
	allowedPanelTitle,
	onPointAdded,
}: {
	containerRef: RefObject<HTMLElement | null>;
	frameWidth?: number;
	frameHeight?: number;
	serviceName?: P2PMeasurementService;
	allowedPanelTitle?: string;
	onPointAdded?: (pointCount: number) => void;
}) {
	const { daiConnection } = useDaiConnection();

	useEffect(() => {
		const host = containerRef.current;
		if (!host) return;

		const onClick = (event: MouseEvent) => {
			const path = (event.composedPath?.() || []) as HTMLElement[];
			if (
				path.some((element) => element?.closest?.('button,[role="button"]'))
			) {
				return;
			}

			const media = path.find(
				(element) =>
					element instanceof HTMLCanvasElement ||
					element instanceof HTMLVideoElement ||
					element instanceof HTMLImageElement,
			) as HTMLCanvasElement | HTMLVideoElement | HTMLImageElement | undefined;

			if (!media) return;

			const panel = media.closest('section') as HTMLElement | null;
			const panelText = panel?.textContent?.trim().toLowerCase() ?? '';
			const allowedTitles = allowedPanelTitle
				? allowedPanelTitle
						.split(',')
						.map((title) => title.trim().toLowerCase())
				: [];
			const isAllowed =
				allowedTitles.length === 0 ||
				allowedTitles.some((title) => panelText.includes(title));

			if (!isAllowed) return;

			const rect = media.getBoundingClientRect();
			const px = event.clientX - rect.left;
			const py = event.clientY - rect.top;
			const aspectRatio = frameWidth / frameHeight;
			const boxAspectRatio = rect.width / rect.height;

			let contentW: number;
			let contentH: number;
			let offX = 0;
			let offY = 0;

			if (boxAspectRatio > aspectRatio) {
				contentH = rect.height;
				contentW = contentH * aspectRatio;
				offX = (rect.width - contentW) / 2;
			} else {
				contentW = rect.width;
				contentH = contentW / aspectRatio;
				offY = (rect.height - contentH) / 2;
			}

			if (
				px < offX ||
				px > offX + contentW ||
				py < offY ||
				py > offY + contentH
			) {
				return;
			}

			const nx = clamp((px - offX) / contentW);
			const ny = clamp((py - offY) / contentH);

			postToP2PMeasurementService(
				daiConnection,
				serviceName,
				{ x: nx, y: ny },
				(response) => {
					const parsedResponse = parseResponse(response);

					if (parsedResponse.ok && onPointAdded) {
						onPointAdded(parsedResponse.point_count ?? -1);
					}
				},
			);
		};

		const onContextMenu = (event: MouseEvent) => {
			const path = (event.composedPath?.() || []) as HTMLElement[];
			const onMedia = path.some(
				(element) =>
					element instanceof HTMLCanvasElement ||
					element instanceof HTMLVideoElement ||
					element instanceof HTMLImageElement,
			);
			if (!onMedia) return;

			event.preventDefault();
			postToP2PMeasurementService(
				daiConnection,
				serviceName,
				{ clear: true },
				(response) => {
					const parsedResponse = parseResponse(response);

					if (parsedResponse.ok && onPointAdded) {
						onPointAdded(0);
					}
				},
			);
		};

		host.addEventListener('click', onClick);
		host.addEventListener('contextmenu', onContextMenu);
		return () => {
			host.removeEventListener('click', onClick);
			host.removeEventListener('contextmenu', onContextMenu);
		};
	}, [
		containerRef,
		frameWidth,
		frameHeight,
		serviceName,
		daiConnection,
		allowedPanelTitle,
		onPointAdded,
	]);

	return null;
}
