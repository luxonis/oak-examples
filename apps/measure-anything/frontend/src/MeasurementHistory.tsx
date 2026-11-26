import { Button, Label, SubHeader, SubLabel } from '@luxonis/ui-components';
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
		<SubLabel
			color="label"
			className="flex h-16 w-20 shrink-0 items-center justify-center overflow-hidden rounded border border-border bg-muted text-center"
		>
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
		</SubLabel>
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
	const cameraDistanceMm = measurement
		? Math.hypot(
				...measurement.cuboid.base_center_mm.map(
					(value, axis) =>
						value +
						(measurement.cuboid.up_axis[axis] *
							measurement.cuboid.dimensions_mm[2]) /
							2,
				),
			)
		: null;
	const trackActive = connected && historyCurrent && record.track_active;
	const waiting = pending || update.isPending;
	return (
		<dialog
			ref={dialog}
			onCancel={onClose}
			aria-labelledby="measurement-title"
			className="fixed inset-0 m-auto max-h-[92dvh] w-[min(1100px,94vw)] overflow-y-auto rounded-xl border border-border bg-background p-6 text-foreground shadow-xl measurement-modal max-[800px]:p-4"
		>
			<div className="mb-5 flex items-start justify-between gap-4">
				<div>
					<h2 id="measurement-title">
						<SubHeader text={`Measurement, Tracking ID ${record.track_id}`} />
					</h2>
					<p className="mt-1">
						<Label color="label">{dimensions(record.dimensions_mm)}</Label>
					</p>
					{cameraDistanceMm !== null ? (
						<p
							className="mt-1"
							title="Straight-line distance from the RGB camera's optical center."
						>
							<Label color="label">
								Camera → cuboid center: {(cameraDistanceMm / 1000).toFixed(3)} m
							</Label>
						</p>
					) : null}
				</div>
				<Button
					type="button"
					onClick={onClose}
					aria-label="Close measurement details"
					variant="outline"
					label="Close"
				/>
			</div>
			<div className="flex flex-wrap items-center gap-3 border-b border-border pb-4 mb-5">
				<Button
					type="button"
					label={
						waiting && trackActive
							? 'Waiting for fresh measurement…'
							: 'Update Measurement'
					}
					disabled={!trackActive || waiting}
					onClick={() => update.mutate({ track_id: record.track_id })}
				/>
				<output>
					<Label color="label">
						{!connected
							? 'Disconnected from device'
							: !historyCurrent
								? 'Waiting for current tracking state.'
								: !trackActive
									? 'Object not in frame'
									: waiting
										? 'The next available frame will replace this saved measurement.'
										: record.in_frame
											? 'Object is in frame. Updates replace the existing snapshot.'
											: 'Tracking active. Waiting for the next observation.'}
					</Label>
				</output>
			</div>
			{update.error ? (
				<p role="alert" className="mt-3">
					<Label color="error">{update.error.message}</Label>
				</p>
			) : null}
			{storageError ? (
				<p role="alert" className="mt-3">
					<Label color="error">{storageError}</Label>
				</p>
			) : null}
			{details.error ? (
				<p role="alert">
					<Label color="error">{details.error.message}</Label>
				</p>
			) : null}
			{!measurement && !details.error ? (
				<p>
					<Label color="normal">Loading saved measurement…</Label>
				</p>
			) : null}
			{measurement ? (
				<>
					<PointCloudViewer measurement={measurement} />
					<dl className="my-5 grid grid-cols-[auto_minmax(0,1fr)] gap-x-5 gap-y-2 max-[600px]:grid-cols-1">
						<dt>
							<Label color="label">Captured</Label>
						</dt>
						<dd>
							<Label>{date(measurement.captured_at)}</Label>
						</dd>
						<dt>
							<Label color="label">Saved</Label>
						</dt>
						<dd>
							<Label>
								{date(measurement.saved_at)}, revision {measurement.revision}
							</Label>
						</dd>
						<dt>
							<Label color="label">Segmented points</Label>
						</dt>
						<dd>
							<Label>{measurement.point_count.toLocaleString()}</Label>
						</dd>
						<dt>
							<Label color="label">Source sequence</Label>
						</dt>
						<dd>
							<Label>
								{measurement.sequence}, RGB {measurement.video_sequence}
							</Label>
						</dd>
						<dt>
							<Label color="label">Measurement status</Label>
						</dt>
						<dd>
							<Label>{measurement.status}</Label>
						</dd>
						<dt>
							<Label color="label">Coordinate reference</Label>
						</dt>
						<dd className="break-all">
							<Label>{measurement.reference_frame}, millimeters</Label>
						</dd>
						<dt>
							<Label color="label">Cuboid base center</Label>
						</dt>
						<dd>
							<Label>
								{measurement.cuboid.base_center_mm
									.map((value) => value.toFixed(1))
									.join(', ')}{' '}
								mm
							</Label>
						</dd>
						<dt>
							<Label color="label">Support plane</Label>
						</dt>
						<dd>
							<Label>
								Normal [
								{measurement.support_plane.normal
									.map((value) => value.toFixed(4))
									.join(', ')}
								], offset {measurement.support_plane.offset_mm.toFixed(1)} mm,
								calibration {measurement.calibration_generation}
							</Label>
						</dd>
						<dt>
							<Label color="label">Algorithm</Label>
						</dt>
						<dd className="break-all">
							<Label>{measurement.algorithm_id}</Label>
						</dd>
						<dt>
							<Label color="label">RGB depth correction</Label>
						</dt>
						<dd className="break-all">
							<Label>
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
							</Label>
						</dd>
					</dl>
				</>
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
			<p>
				<Label color="label">
					Last 20 saved objects. Select an object to inspect its point cloud and
					measurement. History survives app restarts.
				</Label>
			</p>
			{error ? (
				<p role="alert">
					<Label color="error">{error}</Label>
				</p>
			) : null}
			{history.data?.saving_track_id != null ? (
				<output>
					<Label color="normal">
						Saving tracking ID {history.data.saving_track_id}…
					</Label>
				</output>
			) : null}
			{!records.length ? (
				<p className="rounded-lg border border-dashed border-border p-5">
					<Label color="label">
						{history.isLoading
							? 'Loading measurement history…'
							: 'No saved measurements yet. Select a support plane and keep a object in view.'}
					</Label>
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
								<span className="flex justify-between gap-2">
									<Label
										weight="medium"
										text={`Tracking ID ${record.track_id}`}
									/>
									<SubLabel
										color={
											connected && record.track_active ? 'success' : 'label'
										}
									>
										{connected && record.track_active
											? record.in_frame
												? 'In frame'
												: 'Tracking'
											: 'Saved'}
									</SubLabel>
								</span>
								<Label text={dimensions(record.dimensions_mm)} />
								<SubLabel color="label">
									{date(record.captured_at)},{' '}
									{record.point_count.toLocaleString()} points
								</SubLabel>
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
