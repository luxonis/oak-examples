import { Button } from '@luxonis/ui-components';
import { useQueryClient } from '@tanstack/react-query';
import { useEffect, useRef, useState } from 'react';
import { PointCloudViewer } from './PointCloudViewer';
import { daiServiceQueryKey } from './backend/daiService';
import { useDaiMutation } from './backend/useDaiMutation';
import { useDaiQuery } from './backend/useDaiQuery';
import {
	type MeasurementSummary,
	getMeasurement,
	getMeasurementPreview,
	getMeasurements,
	requestMeasurementUpdate,
} from './services';

function dimensions(values: number[]) {
	return `L: ${values[0].toFixed(1)} × W: ${values[1].toFixed(1)} × H: ${values[2].toFixed(1)} mm`;
}

function date(value: string) {
	return new Date(value).toLocaleString();
}

function correctionMetadata(value: unknown) {
	return typeof value === 'string' ? value : 'Not recorded';
}

function MeasurementPreview({ record }: { record: MeasurementSummary }) {
	const preview = useDaiQuery({
		service: getMeasurementPreview,
		request: { track_id: record.track_id, revision: record.revision },
		queryOptions: {
			enabled: record.has_preview,
			staleTime: Number.POSITIVE_INFINITY,
			gcTime: 5 * 60 * 1000,
			retry: 1,
		},
	});
	return (
		<span className="flex h-16 w-20 shrink-0 items-center justify-center overflow-hidden rounded border border-border bg-muted text-center text-xs text-muted-foreground">
			{preview.data?.jpeg ? (
				<img
					src={`data:image/jpeg;base64,${preview.data.jpeg}`}
					alt={`Saved RGB crop of tracking ID ${record.track_id}`}
					className="h-full w-full object-contain"
				/>
			) : !record.has_preview ? (
				'No preview'
			) : preview.error ? (
				'Preview unavailable'
			) : (
				'Loading preview…'
			)}
		</span>
	);
}

function MeasurementModal({
	record,
	connected,
	historyCurrent,
	pending,
	storageError,
	onClose,
}: {
	record: MeasurementSummary;
	connected: boolean;
	historyCurrent: boolean;
	pending: boolean;
	storageError: string | null;
	onClose: () => void;
}) {
	const dialog = useRef<HTMLDialogElement>(null);
	const queryClient = useQueryClient();
	const details = useDaiQuery({
		service: getMeasurement,
		request: { track_id: record.track_id },
		queryOptions: { gcTime: 0, retry: 1 },
	});
	const update = useDaiMutation({
		service: requestMeasurementUpdate,
		mutationOptions: {
			onSuccess: () =>
				queryClient.invalidateQueries({
					queryKey: daiServiceQueryKey(getMeasurements),
				}),
		},
	});
	useEffect(() => {
		const element = dialog.current;
		element?.showModal();
		return () => element?.close();
	}, []);
	const measurement = details.data?.measurement;
	const inFrame = connected && historyCurrent && record.in_frame;
	const waiting = pending || update.isPending;
	return (
		<dialog
			ref={dialog}
			onCancel={onClose}
			aria-labelledby="measurement-title"
			className="fixed inset-0 m-auto max-h-[92dvh] w-[min(1100px,94vw)] overflow-y-auto rounded-xl border border-border bg-background p-6 text-foreground shadow-xl backdrop:bg-black/60 max-[800px]:p-4"
		>
			<div className="mb-5 flex items-start justify-between gap-4">
				<div>
					<h2 id="measurement-title" className="text-xl font-semibold">
						Measurement · Tracking ID {record.track_id}
					</h2>
					<p className="mt-1 text-sm text-muted-foreground">
						{dimensions(record.dimensions_mm)}
					</p>
				</div>
				<button
					type="button"
					onClick={onClose}
					aria-label="Close measurement details"
					className="rounded border border-border px-3 py-1.5"
				>
					Close
				</button>
			</div>
			{details.error ? (
				<p role="alert" className="text-destructive">
					{details.error.message}
				</p>
			) : null}
			{!measurement && !details.error ? (
				<p>Loading saved measurement…</p>
			) : null}
			{measurement ? (
				<>
					<PointCloudViewer measurement={measurement} />
					<dl className="my-5 grid grid-cols-[auto_minmax(0,1fr)] gap-x-5 gap-y-2 text-sm max-[600px]:grid-cols-1">
						<dt className="text-muted-foreground">Captured</dt>
						<dd>{date(measurement.captured_at)}</dd>
						<dt className="text-muted-foreground">Saved</dt>
						<dd>
							{date(measurement.saved_at)} · revision {measurement.revision}
						</dd>
						<dt className="text-muted-foreground">Segmented points</dt>
						<dd>{measurement.point_count.toLocaleString()}</dd>
						<dt className="text-muted-foreground">Source sequence</dt>
						<dd>
							{measurement.sequence} · RGB {measurement.video_sequence}
						</dd>
						<dt className="text-muted-foreground">Measurement status</dt>
						<dd>{measurement.status}</dd>
						<dt className="text-muted-foreground">Coordinate reference</dt>
						<dd className="break-all">
							{measurement.reference_frame} · millimeters
						</dd>
						<dt className="text-muted-foreground">Cuboid base center</dt>
						<dd>
							{measurement.cuboid.base_center_mm
								.map((value) => value.toFixed(1))
								.join(', ')}{' '}
							mm
						</dd>
						<dt className="text-muted-foreground">Support plane</dt>
						<dd>
							Normal [
							{measurement.support_plane.normal
								.map((value) => value.toFixed(4))
								.join(', ')}
							], offset {measurement.support_plane.offset_mm.toFixed(1)} mm ·
							calibration {measurement.calibration_generation}
						</dd>
						<dt className="text-muted-foreground">Algorithm</dt>
						<dd className="break-all">{measurement.algorithm_id}</dd>
						<dt className="text-muted-foreground">RGB depth correction</dt>
						<dd className="break-all">
							{measurement.depth_correction ? (
								<>
									{correctionMetadata(
										measurement.depth_correction.correction_method,
									)}
									<br />
									Input:{' '}
									{correctionMetadata(
										measurement.depth_correction.input_axial_convention,
									)}
									<br />
									Output:{' '}
									{correctionMetadata(
										measurement.depth_correction.output_axial_convention,
									)}
								</>
							) : (
								'Not recorded for this measurement.'
							)}
						</dd>
					</dl>
				</>
			) : null}
			<div className="flex flex-wrap items-center gap-3 border-t border-border pt-4">
				<Button
					type="button"
					label={
						waiting && inFrame
							? 'Waiting for fresh measurement…'
							: 'Update Measurement'
					}
					disabled={!inFrame || waiting}
					onClick={() => update.mutate({ track_id: record.track_id })}
				/>
				<output className="text-sm text-muted-foreground">
					{!connected
						? 'Disconnected from device'
						: !historyCurrent
							? 'Waiting for current tracking state.'
							: !inFrame
								? 'Object not in frame'
								: waiting
									? 'The next available frame will replace this saved measurement.'
									: 'Object is in frame. Updates replace the existing snapshot.'}
				</output>
			</div>
			{update.error ? (
				<p role="alert" className="mt-3 text-sm text-destructive">
					{update.error.message}
				</p>
			) : null}
			{storageError ? (
				<p role="alert" className="mt-3 text-sm text-destructive">
					{storageError}
				</p>
			) : null}
		</dialog>
	);
}

export function MeasurementHistory({ connected }: { connected: boolean }) {
	const history = useDaiQuery({
		service: getMeasurements,
		request: {},
		queryOptions: { refetchInterval: 1000, refetchIntervalInBackground: true },
	});
	const [selected, setSelected] = useState<MeasurementSummary | null>(null);
	const records = history.data?.items ?? [];
	const retained = selected
		? records.find((item) => item.track_id === selected.track_id)
		: null;
	const current = retained ?? selected;
	useEffect(() => {
		if (connected && history.isSuccess && selected && !retained) {
			setSelected(null);
		}
	}, [connected, history.isSuccess, selected, retained]);
	const error =
		history.data?.storage_error ?? (connected ? history.error?.message : null);
	return (
		<section className="flex flex-col gap-3" aria-label="Measurement history">
			<p className="text-sm text-muted-foreground">
				Last 20 saved objects. Select an object to inspect its point cloud and
				measurement. History survives app restarts.
			</p>
			{error ? (
				<p role="alert" className="text-sm text-destructive">
					{error}
				</p>
			) : null}
			{history.data?.saving_track_id != null ? (
				<output className="text-sm">
					Saving tracking ID {history.data.saving_track_id}…
				</output>
			) : null}
			{!records.length ? (
				<p className="rounded-lg border border-dashed border-border p-5 text-sm text-muted-foreground">
					{history.isLoading
						? 'Loading measurement history…'
						: 'No saved measurements yet. Select a support plane and keep a parcel in view.'}
				</p>
			) : null}
			<ol className="flex flex-col gap-2">
				{records.map((record) => (
					<li key={record.track_id}>
						<button
							type="button"
							onClick={() => setSelected(record)}
							className="flex w-full items-center gap-3 rounded-lg border border-border p-3 text-left hover:bg-muted focus-visible:outline-2 focus-visible:outline-primary"
						>
							<MeasurementPreview record={record} />
							<span className="flex min-w-0 flex-1 flex-col gap-1">
								<span className="flex justify-between gap-2 text-sm font-medium">
									<span>Tracking ID {record.track_id}</span>
									<span
										className={
											connected && record.in_frame
												? 'text-success'
												: 'text-muted-foreground'
										}
									>
										{connected && record.in_frame ? 'In frame' : 'Saved'}
									</span>
								</span>
								<span className="text-sm">
									{dimensions(record.dimensions_mm)}
								</span>
								<span className="text-xs text-muted-foreground">
									{date(record.captured_at)} ·{' '}
									{record.point_count.toLocaleString()} points
								</span>
							</span>
						</button>
					</li>
				))}
			</ol>
			{current ? (
				<MeasurementModal
					key={`${current.track_id}-${current.revision}`}
					record={current}
					connected={connected}
					historyCurrent={history.isSuccess && !!retained}
					storageError={history.data?.storage_error ?? null}
					pending={
						history.data?.saving_track_id === current.track_id ||
						!!history.data?.pending_track_ids.includes(current.track_id)
					}
					onClose={() => setSelected(null)}
				/>
			) : null}
		</section>
	);
}
