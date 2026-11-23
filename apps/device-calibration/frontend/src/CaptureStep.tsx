import { Streams } from '@luxonis/depthai-viewer-common';
import { Button, Progress, Switch } from '@luxonis/ui-components';
import type { StepProps } from './api.ts';
import { Section } from './ui.tsx';

const percent = (v: number) => `${Math.round(v * 100)} %`;

/** One stream per enabled socket; the backend draws the coverage overlay. */
export function Main({ state }: StepProps) {
	const topics = Object.entries(state.board.cameras)
		.filter(([, cam]) => cam.enabled)
		.map(([socket]) => socket);
	return (
		<div className="relative min-h-0 flex-1 overflow-hidden">
			<Streams defaultTopics={topics} allowedTopics={topics} />
		</div>
	);
}

export function Side({ state, act }: StepProps) {
	const cap = state.capture;
	if (!cap) return null;
	const name = (socket: string) => state.board.cameras[socket]?.name ?? socket;
	return (
		<>
			<p className="text-lg font-semibold">{cap.guidance.text}</p>

			<Section title="Cameras">
				{Object.entries(cap.cameras).map(([socket, c]) => (
					<div key={socket} className="flex items-center gap-3 text-sm">
						<span className="w-16 shrink-0">{name(socket)}</span>
						<Progress value={c.coverage * 100} />
						<span className="w-12 shrink-0 text-right">
							{percent(c.coverage)}
						</span>
					</div>
				))}
			</Section>

			<Section title="Camera pairs">
				{cap.pairs.map((p) => (
					<button
						key={p.key}
						type="button"
						onClick={() =>
							act('set_view', { pair: p.key === cap.view ? null : p.key })
						}
						className={`flex items-center gap-2 rounded-md px-2 py-1 text-left text-sm hover:bg-muted ${
							p.key === cap.view ? 'bg-muted' : ''
						}`}
					>
						<span
							className={`h-2 w-2 shrink-0 rounded-full ${p.ok ? 'bg-success' : 'bg-warning'}`}
						/>
						<span className="flex-1">
							{name(p.a)} {'<->'} {name(p.b)}
						</span>
						<span className="text-muted-foreground">
							{Math.min(p.shared, p.need)}/{p.need}{' '}
							{percent(Math.min(p.coverageA, p.coverageB))}
						</span>
					</button>
				))}
			</Section>

			<Section title="Poses">
				<div className="flex flex-wrap gap-x-4 gap-y-1 text-sm">
					{Object.entries(cap.poses).map(([pose, { have, need }]) => (
						<span
							key={pose}
							className={
								have >= need ? 'text-success' : 'text-muted-foreground'
							}
						>
							{pose} {have}/{need}
						</span>
					))}
				</div>
			</Section>

			<div className="flex items-center justify-between text-sm">
				<span>Sets: {cap.sets}</span>
				<span className="flex items-center gap-2">
					Auto capture
					<Switch
						value={cap.auto}
						onChange={(value) => act('set_auto', { value })}
						showActiveLabelOnly
					/>
				</span>
			</div>
			<div className="flex gap-2">
				<Button
					className="flex-1"
					variant="outline"
					onClick={() => act('capture')}
					disabled={cap.saving}
				>
					Capture now
				</Button>
				<Button
					className="flex-1"
					variant="outline"
					onClick={() => act('undo_set')}
					disabled={cap.saving || !cap.sets}
				>
					Undo last
				</Button>
				<Button
					className="flex-1"
					variant="outline"
					onClick={() => act('back')}
				>
					Back
				</Button>
			</div>

			{!cap.ready && cap.canProcess && (
				<p className="text-sm text-warning">
					Coverage is incomplete. Processing now can give a weaker calibration.
				</p>
			)}
			<Button
				variant={cap.ready ? 'filled' : 'outline'}
				onClick={() => act('process')}
				disabled={!cap.canProcess}
			>
				Process
			</Button>
			{state.message && (
				<p
					className={`text-sm ${state.messageOk ? 'text-success' : 'text-destructive'}`}
				>
					{state.message}
				</p>
			)}
		</>
	);
}

export function ProcessingMain({ state }: StepProps) {
	const p = state.processing;
	return (
		<div className="flex flex-1 flex-col items-center justify-center gap-3">
			<div className="w-full max-w-md">
				<Progress value={(p?.progress ?? 0) * 100} />
			</div>
			<p className="text-sm text-muted-foreground">{p?.stage}</p>
		</div>
	);
}

export function ProcessingSide({ state, act }: StepProps) {
	return (
		<>
			<Section title="Processing">
				<p className="text-sm">{state.processing?.stage}</p>
			</Section>
			<Button variant="outline" onClick={() => act('cancel')}>
				Cancel
			</Button>
		</>
	);
}
