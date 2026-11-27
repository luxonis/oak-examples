import { Streams, useDaiConnection } from '@luxonis/depthai-viewer-common';
import {
	Button,
	Card,
	Label,
	NormalText,
	StyledText,
	SubLabel,
} from '@luxonis/ui-components';
import { useQueryClient } from '@tanstack/react-query';
import { useEffect, useRef, useState } from 'react';
import './App.css';
import { AppShell } from './AppShell';
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
				<div className="flex aspect-[4/3] w-full items-center justify-center rounded bg-muted">
					<Label
						color="label"
						text={preview.error ? preview.error.message : 'Loading preview…'}
					/>
				</div>
			)}
			<div className="flex w-full items-center justify-between gap-2">
				<Label text={`Candidate ${candidate.index + 1}`} />
				{candidate.recommended ? (
					<SubLabel color="success" text="Most inliers" />
				) : null}
			</div>
			<SubLabel
				color="label"
				text={`${candidate.inlier_count.toLocaleString()} inliers (${(100 * candidate.inlier_ratio).toFixed(1)}%)`}
			/>
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
	const frameError =
		state?.frame?.failure_code != null ? state.frame.message : '';

	return (
		<AppShell
			title="Measure anything"
			streams={
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
			}
		>
			<div className="measurement-controls">
				<Label text="Measure objects on a fixed, flat support surface. Objects appear after 10 consecutive observations." />
				<section aria-label="Processing">
					<Card
						title="Processing"
						variant="outline"
						intent="white"
						contentClassName="flex flex-col gap-3"
					>
						<div className="flex justify-between gap-2">
							<Label text="Capture" />
							<Label text={rate(state?.rates.source_fps)} />
						</div>
						<div className="flex justify-between gap-2">
							<Label text="Measurements" />
							<Label text={rate(state?.rates.measurement_fps)} />
						</div>
						<Label
							text={`Capture is configured at ${state?.capture.configured_fps ?? 10} FPS. Measurement throughput depends on the scene and CPU. Video follows the matching measured frame.`}
						/>
						<Label
							role="status"
							aria-live="polite"
							aria-atomic="true"
							color="error"
							className="processing-frame-status"
							text={frameError}
							title={frameError || undefined}
						/>
					</Card>
				</section>

				<div
					role="tablist"
					aria-label="Measurement controls"
					className="flex shrink-0 rounded-lg border border-border p-1"
				>
					{CONTROL_TABS.map(({ id: value, label }, index) => (
						<Button
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
							className="flex-1"
							variant={tab === value ? 'filled' : 'ghost'}
							intent={tab === value ? 'active' : 'gray'}
							label={label}
						/>
					))}
				</div>
				<div className="measurement-panels">
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
								className="rounded-lg border border-destructive p-3"
							>
								<Label
									color="error"
									text="Support plane verification failed. Recalibrate before measuring more objects."
								/>
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
							className="flex flex-col gap-2 rounded-lg border border-border p-3"
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
								<Label text="Colorized depth over RGB" />
							</label>
							{state?.overlays.depth ? (
								<SubLabel
									color="label"
									text="Depth colors are blended at 50% opacity. One overlay is shown at a time."
								/>
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
								<Label text="Show selected support plane" />
							</label>
						</section>
					</section>
					{error ? (
						<div role="alert">
							<StyledText size="label" color="error" text={error} />
						</div>
					) : null}
				</div>
			</div>
		</AppShell>
	);
}

export default App;
