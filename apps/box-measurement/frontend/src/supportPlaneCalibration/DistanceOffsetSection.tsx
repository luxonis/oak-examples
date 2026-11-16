import {
	AddIcon,
	Button,
	Input,
	Label,
	StyledText,
	SubLabel,
} from '@luxonis/ui-components';
import { useId, useState } from 'react';

import PanelSection from '../components/PanelSection';
import RemoveIcon from '../components/RemoveIcon';
import { cmToMm, roundCmToMm } from '../units';
import {
	MAX_DISTANCE_OFFSET_CM,
	useSetDistanceOffset,
} from './useSupportPlaneCalibration';

const OFFSET_STEP_CM = 0.1;

type DistanceOffsetSectionProps = {
	/** Detected camera-to-support-plane distance along the optical axis. */
	cameraDistanceCm: number;
	offsetCm: number;
};

// Parses the typed offset; null while it is not a valid offset.
// Accepts both "." and "," so the decimal separator does not depend on locale.
const parseOffsetCm = (draft: string): number | null => {
	const normalized = draft.trim().replace(',', '.');
	if (normalized === '') {
		return null;
	}
	const offsetCm = roundCmToMm(Number(normalized));
	if (
		!Number.isFinite(offsetCm) ||
		Math.abs(offsetCm) > MAX_DISTANCE_OFFSET_CM
	) {
		return null;
	}
	return offsetCm;
};

const clampOffsetCm = (offsetCm: number) =>
	Math.min(MAX_DISTANCE_OFFSET_CM, Math.max(-MAX_DISTANCE_OFFSET_CM, offsetCm));

const RANGE_TEXT = `−${MAX_DISTANCE_OFFSET_CM} to +${MAX_DISTANCE_OFFSET_CM} cm`;

function DistanceOffsetSection({
	cameraDistanceCm,
	offsetCm,
}: DistanceOffsetSectionProps) {
	const rangeHintId = useId();
	const distanceOffsetMutation = useSetDistanceOffset();
	const { isPending, error } = distanceOffsetMutation;
	// Text input so it always shows "0.0", regardless of the browser locale.
	// Starts from the applied offset; the view remounts after Recalibrate.
	const [draft, setDraft] = useState(() => offsetCm.toFixed(1));
	const draftOffsetCm = parseOffsetCm(draft);
	const isDraftInvalid = draft.trim() !== '' && draftOffsetCm === null;

	const apply = (value: number) => {
		distanceOffsetMutation.mutate(
			{ offset_mm: cmToMm(value) },
			{ onSuccess: () => setDraft(value.toFixed(1)) },
		);
	};

	const step = (direction: 1 | -1) => {
		const current = draftOffsetCm ?? offsetCm;
		const next = clampOffsetCm(
			roundCmToMm(current + direction * OFFSET_STEP_CM),
		);
		setDraft(next.toFixed(1));
	};

	return (
		<PanelSection title="Distance offset">
			<form
				className="flex w-full flex-col gap-3"
				onSubmit={(event) => {
					event.preventDefault();
					if (draftOffsetCm !== null) {
						apply(draftOffsetCm);
					}
				}}
			>
				<div className="flex items-center justify-between gap-2">
					<Label text="Detected distance" color="normal" />
					<Label text={`${cameraDistanceCm.toFixed(1)} cm`} />
				</div>
				<div className="flex flex-col gap-1">
					<SubLabel
						text={
							<>
								<strong>How to measure:</strong> Measure from the camera to the
								support plane along the camera’s viewing direction.
							</>
						}
					/>
					<SubLabel text="Offset = measured distance − detected distance." />
					<SubLabel text="Positive values move the support plane farther away." />
				</div>
				<div className="flex flex-col gap-1">
					<div className="flex items-center justify-between gap-2">
						<Label text="Offset (cm)" color="normal" />
						<div className="flex items-center gap-1">
							<Button
								type="button"
								variant="outline"
								size="icon"
								icon={RemoveIcon}
								label={null}
								aria-label="Decrease offset"
								disabled={isPending}
								onClick={() => step(-1)}
							/>
							<Input
								type="text"
								inputMode="decimal"
								autoComplete="off"
								aria-label="Distance offset in cm"
								aria-invalid={isDraftInvalid}
								aria-describedby={rangeHintId}
								className="w-[4.5rem] text-center"
								value={draft}
								disabled={isPending}
								onChange={(event) => setDraft(event.target.value)}
								onKeyDown={(event) => {
									if (event.key === 'ArrowUp') {
										event.preventDefault();
										step(1);
									} else if (event.key === 'ArrowDown') {
										event.preventDefault();
										step(-1);
									}
								}}
							/>
							<Button
								type="button"
								variant="outline"
								size="icon"
								icon={AddIcon}
								label={null}
								aria-label="Increase offset"
								disabled={isPending}
								onClick={() => step(1)}
							/>
						</div>
					</div>
					{isDraftInvalid ? (
						<StyledText
							id={rangeHintId}
							size="label"
							color="error"
							text={`Enter a number from ${RANGE_TEXT}.`}
						/>
					) : (
						<SubLabel id={rangeHintId} text={`Allowed range: ${RANGE_TEXT}.`} />
					)}
				</div>
				<div className="flex items-center justify-between gap-2">
					<Label text="Distance with offset" color="normal" />
					<Label
						weight="bold"
						text={
							draftOffsetCm === null
								? '–'
								: `${(cameraDistanceCm + draftOffsetCm).toFixed(1)} cm`
						}
					/>
				</div>
				{error ? (
					<StyledText size="label" color="error" text={error.message} />
				) : null}
				<div className="flex justify-end gap-2">
					<Button
						type="button"
						variant="outline"
						label="Clear offset"
						disabled={isPending || offsetCm === 0}
						onClick={() => {
							setDraft('0.0');
							apply(0);
						}}
					/>
					<Button
						type="submit"
						variant="filled"
						label="Apply"
						disabled={
							isPending || draftOffsetCm === null || draftOffsetCm === offsetCm
						}
					/>
				</div>
			</form>
		</PanelSection>
	);
}

export default DistanceOffsetSection;
