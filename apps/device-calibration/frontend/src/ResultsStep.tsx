import { Button } from '@luxonis/ui-components';
import type { ReactNode } from 'react';
import type { CameraResult, StepProps } from './api.ts';
import { Section } from './ui.tsx';

const px = (v: number | null) => (v === null ? 'n/a' : v.toFixed(2));

/** Old vs new rows that can be compared. */
function comparisons(r: CameraResult): [number, number | null][] {
	return [
		...r.cameras.map((c): [number, number | null] => [c.rmsNew, c.rmsOld]),
		...r.pairs.map((p): [number, number | null] => [p.newPx, p.oldPx]),
		...(r.stereo
			? [
					[r.stereo.epipolarNew, r.stereo.epipolarOld] as [
						number,
						number | null,
					],
				]
			: []),
	].filter(([, old]) => old !== null);
}

function Table({ head, rows }: { head: string[]; rows: ReactNode[][] }) {
	return (
		<table className="w-full text-sm">
			<thead>
				<tr className="text-left text-muted-foreground">
					{head.map((h) => (
						<th key={h} className="font-normal">
							{h}
						</th>
					))}
				</tr>
			</thead>
			<tbody>
				{rows.map((row) => (
					<tr key={String(row[0])} className="border-t border-border">
						{row.map((cell, i) => (
							<td key={head[i]}>{cell}</td>
						))}
					</tr>
				))}
			</tbody>
		</table>
	);
}

/** Green when the new value beats the stored one. */
function delta(newPx: number, oldPx: number | null) {
	if (oldPx === null) return 'n/a';
	const d = newPx - oldPx;
	return (
		<span className={d < 0 ? 'text-success' : 'text-warning'}>
			{d > 0 ? '+' : ''}
			{d.toFixed(2)}
		</span>
	);
}

export function Main({ state }: StepProps) {
	const r = state.cameraResult;
	if (!r) return null;
	const name = (socket: string) =>
		r.cameras.find((c) => c.socket === socket)?.name ?? socket;
	return (
		<div className="flex min-h-0 flex-1 flex-col gap-5 overflow-y-auto">
			<Section title="Cameras">
				<Table
					head={[
						'Camera',
						'Model',
						'Views',
						'Coverage',
						'RMS old (px)',
						'RMS new (px)',
					]}
					rows={r.cameras.map((c) => [
						c.name,
						c.model,
						String(c.views),
						`${Math.round(c.coverage * 100)} %`,
						px(c.rmsOld),
						px(c.rmsNew),
					])}
				/>
			</Section>
			<Section title="Cross-camera reprojection">
				<Table
					head={['From -> to', 'Views', 'Old (px)', 'New (px)', 'Delta']}
					rows={r.pairs.map((p) => [
						`${name(p.from)} -> ${name(p.to)}`,
						String(p.views),
						px(p.oldPx),
						px(p.newPx),
						delta(p.newPx, p.oldPx),
					])}
				/>
			</Section>
			{r.stereo && (
				<Section title="Stereo epipolar error">
					<Table
						head={['Pair', 'Old (px)', 'New (px)', 'Delta']}
						rows={[
							[
								`${name(r.stereo.left)} / ${name(r.stereo.right)}`,
								px(r.stereo.epipolarOld),
								px(r.stereo.epipolarNew),
								delta(r.stereo.epipolarNew, r.stereo.epipolarOld),
							],
						]}
					/>
				</Section>
			)}
			{r.problems.map((p) => (
				<p key={p} className="text-sm text-destructive">
					{p}
				</p>
			))}
			{r.warnings.map((w) => (
				<p key={w} className="text-sm text-warning">
					{w}
				</p>
			))}
		</div>
	);
}

export function Side({ state, act }: StepProps) {
	const r = state.cameraResult;
	if (!r) return null;
	const checks = comparisons(r);
	const better = checks.filter(([n, o]) => o !== null && n < o).length;
	return (
		<>
			<Section title="Verdict">
				<p className="text-sm">
					New calibration is better on {better} of {checks.length} checks.
				</p>
			</Section>
			<Button onClick={() => act('accept')} disabled={r.problems.length > 0}>
				{state.imu ? 'Continue to IMU' : 'Continue to review'}
			</Button>
			<div className="flex gap-2">
				<Button
					className="flex-1"
					variant="outline"
					onClick={() => act('recapture')}
				>
					Capture more
				</Button>
				<Button
					className="flex-1"
					variant="outline"
					onClick={() => act('discard')}
				>
					Discard
				</Button>
			</div>
		</>
	);
}
