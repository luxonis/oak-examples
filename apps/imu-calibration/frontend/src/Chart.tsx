import { useEffect, useRef } from 'react';
import type { Vec3 } from './api.ts';

export const AXIS_COLORS = ['#ef4444', '#22c55e', '#3b82f6'];

export interface Series {
	values: Vec3[];
	dashed?: boolean;
}

interface ChartProps {
	title: string;
	unit: string;
	series: Series[];
	window: number;
	/** Smallest y-range shown, so sensor noise is not blown up to full height. */
	minSpan: number;
	placeholder?: string;
}

export function Chart({
	title,
	unit,
	series,
	window,
	minSpan,
	placeholder,
}: ChartProps) {
	const canvasRef = useRef<HTMLCanvasElement>(null);

	useEffect(() => {
		const canvas = canvasRef.current;
		const ctx = canvas?.getContext('2d');
		if (!canvas || !ctx) return;
		const { width, height } = canvas.getBoundingClientRect();
		const dpr = globalThis.devicePixelRatio || 1;
		canvas.width = width * dpr;
		canvas.height = height * dpr;
		ctx.scale(dpr, dpr);
		ctx.clearRect(0, 0, width, height);

		const all = series.flatMap((s) => s.values.flat());
		if (!all.length) return;
		let lo = Math.min(...all);
		let hi = Math.max(...all);
		const pad = Math.max(minSpan - (hi - lo), 0) / 2 + (hi - lo) * 0.05;
		lo -= pad;
		hi += pad;
		const y = (v: number) => height - ((v - lo) / (hi - lo)) * height;
		const step = width / (window - 1);

		for (const s of series) {
			ctx.setLineDash(s.dashed ? [5, 4] : []);
			ctx.globalAlpha = s.dashed ? 0.55 : 1;
			for (let axis = 0; axis < 3; axis++) {
				ctx.strokeStyle = AXIS_COLORS[axis];
				ctx.beginPath();
				const offset = width - (s.values.length - 1) * step;
				s.values.forEach((v, i) => {
					ctx.lineTo(offset + i * step, y(v[axis]));
				});
				ctx.stroke();
			}
		}
		ctx.setLineDash([]);
		ctx.globalAlpha = 1;
		// Range labels go last, on a backdrop, so they stay readable over the traces.
		ctx.font = '11px sans-serif';
		for (const [text, top] of [
			[hi.toFixed(2), 0],
			[lo.toFixed(2), height - 15],
		] as const) {
			ctx.fillStyle = 'rgba(255,255,255,0.85)';
			ctx.fillRect(0, top, ctx.measureText(text).width + 8, 15);
			ctx.fillStyle = '#6b7280';
			ctx.fillText(text, 4, top + 11);
		}
	}, [series, window, minSpan]);

	return (
		<div className="flex min-h-0 flex-1 flex-col rounded-md border border-gray-200 bg-white p-2">
			<div className="flex items-center justify-between text-sm">
				<span className="font-semibold">
					{title} <span className="font-normal text-gray-500">[{unit}]</span>
				</span>
				<span className="flex gap-3 text-xs">
					{['x', 'y', 'z'].map((axis, i) => (
						<span key={axis} style={{ color: AXIS_COLORS[i] }}>
							● {axis}
						</span>
					))}
				</span>
			</div>
			{placeholder ? (
				<div className="flex flex-1 items-center justify-center text-sm text-gray-500">
					{placeholder}
				</div>
			) : (
				<canvas ref={canvasRef} className="min-h-0 w-full flex-1" />
			)}
		</div>
	);
}
