import { Streams, useDaiConnection } from '@luxonis/depthai-viewer-common';
import {
	Button,
	Header,
	Label,
	NormalText,
	StyledText,
} from '@luxonis/ui-components';
import { useQueryClient } from '@tanstack/react-query';
import { useState } from 'react';
import { daiServiceQueryKey } from './backend/daiService';
import { useDaiMutation } from './backend/useDaiMutation';
import { useDaiQuery } from './backend/useDaiQuery';
import {
	type PlaneCandidate,
	calibrateSupportPlane,
	getParcelState,
	getSupportPlanePreview,
	selectSupportPlane,
} from './services';

const VIDEO_TOPIC = 'Color stream';
const ANNOTATIONS_TOPIC = 'Parcel annotations';
const TOPICS = [VIDEO_TOPIC, ANNOTATIONS_TOPIC];

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
	const [candidateSelection, setCandidateSelection] = useState<{
		generation: number;
		index: number;
	} | null>(null);
	const stateQuery = useDaiQuery({
		service: getParcelState,
		request: {},
		queryOptions: {
			refetchInterval: 500,
			refetchIntervalInBackground: true,
		},
	});
	const refreshState = () =>
		queryClient.invalidateQueries({
			queryKey: daiServiceQueryKey(getParcelState),
		});
	const calibrate = useDaiMutation({
		service: calibrateSupportPlane,
		mutationOptions: { onSuccess: refreshState },
	});
	const select = useDaiMutation({
		service: selectSupportPlane,
		mutationOptions: { onSuccess: refreshState },
	});
	const state = stateQuery.data;
	const calibration = state?.calibration;
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
			<aside className="flex max-h-full w-[420px] shrink-0 flex-col gap-5 overflow-y-auto pr-2 text-left max-[800px]:max-h-none max-[800px]:w-full max-[800px]:overflow-visible max-[800px]:pr-0">
				<h1>
					<Header text="Parcel measurement" />
				</h1>
				<Label text="Measure parcels on a fixed, flat support surface. RGB boxes show tracking IDs and length × width × height in millimeters." />
				<section className="flex flex-col gap-3">
					<h2>
						<NormalText weight="bold" text="Support plane" />
					</h2>
					<Label text={calibration?.message ?? 'Connecting to the camera…'} />
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
						<Label text="Keep the camera fixed. Recalibrate after moving it or changing the support surface. Unknown heights appear as ?." />
					) : null}
				</section>
				{error ? (
					<div role="alert">
						<StyledText size="label" color="error" text={error} />
					</div>
				) : null}
				<section className="flex flex-col gap-3 border-t border-border pt-4">
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
					className={`mt-auto flex items-center gap-2 border-t border-border pt-4 text-sm ${connected ? 'text-success' : 'text-destructive'}`}
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
