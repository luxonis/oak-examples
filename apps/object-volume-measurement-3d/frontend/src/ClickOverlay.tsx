import { useDaiConnection } from '@luxonis/depthai-viewer-common';
import type { RefObject } from 'react';
import { useEffect } from 'react';
import {
	type ObjectVolumeService,
	postToObjectVolumeService,
} from './services.ts';

const clamp = (value: number) => Math.max(0, Math.min(1, value));

export function ClickCatcher({
	containerRef,
	frameWidth = 640,
	frameHeight = 640,
	serviceName = 'Selection Service',
	debug = false,
	allowedPanelTitle,
}: {
	containerRef: RefObject<HTMLElement | null>;
	frameWidth?: number;
	frameHeight?: number;
	serviceName?: ObjectVolumeService;
	allowedPanelTitle?: string;
	debug?: boolean;
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

			if (debug) {
				console.log('[ClickCatcher] panelText:', panelText);
				console.log('[ClickCatcher] allowedPanelTitle:', allowedPanelTitle);
			}

			if (
				allowedPanelTitle &&
				!panelText.includes(allowedPanelTitle.toLowerCase())
			) {
				if (debug) console.log('ignored: panel text mismatch');
				return;
			}

			const looks3D =
				media instanceof HTMLCanvasElement &&
				(media.hasAttribute('data-camera-controls-version') ||
					getComputedStyle(media).touchAction === 'none');

			if (looks3D) {
				if (debug) console.log('ignored: 3D/Pointcloud canvas');
				return;
			}

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
				if (debug) console.log('ignored letterbox click');
				return;
			}

			const nx = clamp((px - offX) / contentW);
			const ny = clamp((py - offY) / contentH);

			if (debug) console.log('norm(image only):', { nx, ny });

			postToObjectVolumeService(
				daiConnection,
				serviceName,
				{ x: nx, y: ny },
				(response) => {
					if (debug) console.log('ack:', response);
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
			postToObjectVolumeService(daiConnection, serviceName, { clear: true });
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
		debug,
		daiConnection,
		allowedPanelTitle,
	]);

	return null;
}
