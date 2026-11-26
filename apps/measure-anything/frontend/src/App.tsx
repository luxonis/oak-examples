import { Streams, useDaiConnection } from '@luxonis/depthai-viewer-common';
import {
	Button,
	Header,
	Label,
	NormalText,
	StyledText,
} from '@luxonis/ui-components';
import { useQueryClient } from '@tanstack/react-query';
import { useEffect, useRef, useState } from 'react';
import { MeasurementHistory } from './MeasurementHistory';
import { daiServiceQueryKey } from './backend/daiService';
import { useDaiMutation } from './backend/useDaiMutation';
import { useDaiQuery } from './backend/useDaiQuery';
import {
	type PlaneCandidate,
	calibrateSupportPlane,
	getMeasurementState,
	getSupportPlanePreview,
	selectSupportPlane,
	setPreviewOptions,
} from './services';

const VIDEO_TOPIC = 'Color stream';
const ANNOTATIONS_TOPIC = 'Object annotations';
const TOPICS = [VIDEO_TOPIC, ANNOTATIONS_TOPIC];
const CONTROL_TABS = [
	{ id: 'calibration', label: 'Calibration' },
	{ id: 'measurements', label: 'Measurements' },
	{ id: 'configuration', label: 'Configuration' },
] as const;

function CandidatePreview({
	generation,
	candidate,
	selected,
	onSelect,
}: {
	generation: number;
	candidate: PlaneCandidate;
	selected: boolean;
	onSelect: () => void;
}) {
	const preview = useDaiQuery({
		service: getSupportPlanePreview,
		request: { generation, index: candidate.index },
		queryOptions: { staleTime: Number.POSITIVE_INFINITY, gcTime: 0, retry: 1 },
	});
	return (
		<button
			type="button"
			aria-pressed={selected}
			onClick={onSelect}
			className={`flex w-full flex-col gap-2 rounded-lg border p-2 text-left ${
				selected ? 'border-primary ring-1 ring-primary' : 'border-border'
			}`}
		>
			{preview.data ? (
				<img
					src={`data:image/jpeg;base64,${preview.data.jpeg}`}
					alt={`Support plane candidate ${candidate.index + 1} with green surface inliers`}
					className="aspect-[4/3] w-full rounded object-contain"
				/>
			) : (
				<div className="flex aspect-[4/3] w-full items-center justify-center rounded bg-muted text-sm text-muted-foreground">
					{preview.error ? preview.error.message : 'Loading preview…'}
				</div>
			)}
			<div className="flex w-full items-center justify-between gap-2 text-sm">
				<span>Candidate {candidate.index + 1}</span>
				{candidate.recommended ? (
					<span className="text-success">Most inliers</span>
				) : null}
			</div>
			<span className="text-xs text-muted-foreground">
				{candidate.inlier_count.toLocaleString()} inliers ·{' '}
				{(100 * candidate.inlier_ratio).toFixed(1)}%
			</span>
		</button>
	);
}

function rate(value?: number | null) {
	return value == null ? 'Waiting' : `${value.toFixed(1)} FPS`;
}

function App() {
	const { connected } = useDaiConnection();
	const queryClient = useQueryClient();
	const [tab, setTab] =
		useState<(typeof CONTROL_TABS)[number]['id']>('calibration');
	const [candidateSelection, setCandidateSelection] = useState<{
		generation: number;
		index: number;
	} | null>(null);
	const stateQuery = useDaiQuery({
		service: getMeasurementState,
		request: {},
		queryOptions: {
			refetchInterval: 500,
			refetchIntervalInBackground: true,
		},
	});
	const refreshState = () =>
		queryClient.invalidateQueries({
			queryKey: daiServiceQueryKey(getMeasurementState),
		});
	const calibrate = useDaiMutation({
		service: calibrateSupportPlane,
		mutationOptions: { onSuccess: refreshState },
	});
	const select = useDaiMutation({
		service: selectSupportPlane,
		mutationOptions: { onSuccess: refreshState },
	});
	const previewOptions = useDaiMutation({
		service: setPreviewOptions,
		mutationOptions: { onSuccess: refreshState },
	});
	const state = stateQuery.data;
	const calibration = state?.calibration;
	const promptedGeneration = useRef<number | null>(null);
	useEffect(() => {
		if (
			calibration?.recalibration_required &&
			promptedGeneration.current !== calibration.generation
		) {
			promptedGeneration.current = calibration.generation;
			setTab('calibration');
			setCandidateSelection(null);
		}
	}, [calibration?.recalibration_required, calibration?.generation]);
	const choosing = calibration?.phase === 'choosing';
	const calibrating = calibration?.phase === 'calibrating';
	const selected =
		candidateSelection?.generation === calibration?.generation
			? candidateSelection
			: null;
	const error =
		state?.error ??
		calibrate.error?.message ??
		select.error?.message ??
		previewOptions.error?.message ??
		(connected ? stateQuery.error?.message : null);

	return (
		<main className="flex h-dvh w-full flex-row gap-6 bg-background p-6 max-[800px]:h-auto max-[800px]:min-h-dvh max-[800px]:flex-col max-[800px]:gap-5 max-[800px]:p-4">
			<div className="relative min-h-0 min-w-0 flex-1 overflow-hidden max-[800px]:h-[55dvh] max-[800px]:min-h-[260px] max-[800px]:flex-none">
				<Streams
					defaultTopics={TOPICS}
					topicGroups={{
						[VIDEO_TOPIC]: 'preview',
						[ANNOTATIONS_TOPIC]: 'preview',
					}}
					numberOfColumns={1}
					topicSortingFunction={(a, b) =>
						TOPICS.indexOf(a.name) - TOPICS.indexOf(b.name)
					}
				/>
			</div>
			<div className="w-0.5 shrink-0 bg-border max-[800px]:h-0.5 max-[800px]:w-full" />
			<aside className="flex min-h-0 max-h-full w-[420px] shrink-0 flex-col gap-5 overflow-hidden pr-2 text-left max-[800px]:max-h-none max-[800px]:w-full max-[800px]:overflow-visible max-[800px]:pr-0">
				<div className="flex shrink-0 flex-col gap-5">
					<h1>
						<Header text="Measure anything" />
					</h1>
					<Label text="Measure objects on a fixed, flat support surface. Objects appear after 10 consecutive observations." />
				</div>
				<section
					aria-label="Processing"
					className="flex shrink-0 flex-col gap-3 border-t border-border pt-4"
				>
					<h2>
						<NormalText weight="bold" text="Processing" />
					</h2>
					<div className="flex justify-between gap-2 text-sm">
						<span>Capture</span>
						<span>{rate(state?.rates.source_fps)}</span>
					</div>
					<div className="flex justify-between gap-2 text-sm">
						<span>Measurements</span>
						<span>{rate(state?.rates.measurement_fps)}</span>
					</div>
					<Label
						text={`Capture is configured at ${state?.capture.configured_fps ?? 10} FPS. Measurement throughput depends on the scene and CPU. Video follows the matching measured frame.`}
					/>
					{calibration?.phase === 'ready' && state?.frame ? (
						<Label text={state.frame.message} />
					) : null}
				</section>

				<div
					role="tablist"
					aria-label="Measurement controls"
					className="flex shrink-0 rounded-lg border border-border p-1"
				>
					{CONTROL_TABS.map(({ id: value, label }, index) => (
						<button
							key={value}
							id={`${value}-tab`}
							type="button"
							role="tab"
							aria-selected={tab === value}
							aria-controls={`${value}-panel`}
							tabIndex={tab === value ? 0 : -1}
							onClick={() => setTab(value)}
							onKeyDown={(event) => {
								if (
									['ArrowLeft', 'ArrowRight', 'Home', 'End'].includes(event.key)
								) {
									event.preventDefault();
									const next =
										event.key === 'Home'
											? CONTROL_TABS[0].id
											: event.key === 'End'
												? CONTROL_TABS[CONTROL_TABS.length - 1].id
												: CONTROL_TABS[
														(index +
															(event.key === 'ArrowRight' ? 1 : -1) +
															CONTROL_TABS.length) %
															CONTROL_TABS.length
													].id;
									setTab(next);
									document.getElementById(`${next}-tab`)?.focus();
								}
							}}
							className={`flex-1 rounded-md px-3 py-2 text-sm ${tab === value ? 'bg-muted font-semibold' : 'text-muted-foreground'}`}
						>
							{label}
						</button>
					))}
				</div>
				<div className="min-h-0 flex-1 overflow-y-auto pr-1 max-[800px]:flex-none max-[800px]:overflow-visible max-[800px]:pr-0">
					<section
						id="calibration-panel"
						role="tabpanel"
						aria-labelledby="calibration-tab"
						hidden={tab !== 'calibration'}
						className={tab === 'calibration' ? 'flex flex-col gap-3' : 'hidden'}
					>
						<h2>
							<NormalText weight="bold" text="Support plane" />
						</h2>
						<Label text={calibration?.message ?? 'Connecting to the camera…'} />
						{calibration?.recalibration_required ? (
							<div
								role="alert"
								className="rounded-lg border border-destructive p-3 text-sm text-destructive"
							>
								Support plane verification failed. Recalibrate before measuring
								more objects.
							</div>
						) : null}
						<Button
							type="button"
							variant="outline"
							label={
								calibrating
									? 'Finding support planes…'
									: calibration?.phase === 'idle'
										? 'Find support planes'
										: 'Recalibrate'
							}
							disabled={
								!connected ||
								!state ||
								calibrating ||
								calibrate.isPending ||
								select.isPending
							}
							onClick={() => {
								setCandidateSelection(null);
								select.reset();
								calibrate.mutate({});
							}}
						/>
						{choosing && calibration ? (
							<>
								<Label text="Select the supporting table or floor. Green pixels mark each candidate surface." />
								<div className="grid grid-cols-2 gap-3">
									{calibration.candidates.map((candidate) => (
										<CandidatePreview
											key={`${calibration.generation}-${candidate.index}`}
											generation={calibration.generation}
											candidate={candidate}
											selected={selected?.index === candidate.index}
											onSelect={() =>
												setCandidateSelection({
													generation: calibration.generation,
													index: candidate.index,
												})
											}
										/>
									))}
								</div>
								<Button
									type="button"
									label="Use this support plane"
									disabled={
										!connected ||
										!selected ||
										select.isPending ||
										calibrate.isPending
									}
									onClick={() => {
										if (selected) select.mutate(selected);
									}}
								/>
							</>
						) : null}
						{calibration?.phase === 'ready' ? (
							<Label text="The support plane is checked every 5 seconds. Keep the camera fixed. Unknown heights appear as ?." />
						) : null}
					</section>
					<section
						id="measurements-panel"
						role="tabpanel"
						aria-labelledby="measurements-tab"
						hidden={tab !== 'measurements'}
						className={tab === 'measurements' ? 'block' : 'hidden'}
					>
						{tab === 'measurements' ? (
							<MeasurementHistory connected={connected} />
						) : null}
					</section>
					<section
						id="configuration-panel"
						role="tabpanel"
						aria-labelledby="configuration-tab"
						hidden={tab !== 'configuration'}
						className={tab === 'configuration' ? 'block' : 'hidden'}
					>
						<section
							aria-label="RGB overlays"
							className="flex flex-col gap-2 rounded-lg border border-border p-3 text-sm"
						>
							<label className="flex items-center gap-2">
								<input
									type="checkbox"
									checked={state?.overlays.depth ?? false}
									disabled={!connected || !state || previewOptions.isPending}
									onChange={(event) => {
										if (state)
											previewOptions.mutate({
												...state.overlays,
												depth: event.target.checked,
												support_plane: event.target.checked
													? false
													: state.overlays.support_plane,
											});
									}}
								/>
								Colorized depth over RGB
							</label>
							{state?.overlays.depth ? (
								<span className="text-xs text-muted-foreground">
									Depth colors are blended at 50% opacity. One overlay is shown
									at a time.
								</span>
							) : null}
							<label className="flex items-center gap-2">
								<input
									type="checkbox"
									checked={state?.overlays.support_plane ?? false}
									disabled={
										!connected ||
										calibration?.phase !== 'ready' ||
										previewOptions.isPending
									}
									onChange={(event) => {
										if (state)
											previewOptions.mutate({
												...state.overlays,
												support_plane: event.target.checked,
												depth: event.target.checked
													? false
													: state.overlays.depth,
											});
									}}
								/>
								Show selected support plane
							</label>
						</section>
					</section>
					{error ? (
						<div role="alert">
							<StyledText size="label" color="error" text={error} />
						</div>
					) : null}
				</div>
				<div
					className={`mt-auto flex shrink-0 items-center gap-2 border-t border-border pt-4 text-sm ${connected ? 'text-success' : 'text-destructive'}`}
				>
					<span
						className={`h-2 w-2 rounded-full ${connected ? 'bg-success' : 'bg-destructive'}`}
					/>
					<span>{connected ? 'Connected to device' : 'Disconnected'}</span>
				</div>
			</aside>
		</main>
	);
}

export default App;
