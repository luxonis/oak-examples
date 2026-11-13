import {
	AddIcon,
	Button,
	Input,
	Label,
	SettingsIcon,
	StyledText,
	SubLabel,
} from '@luxonis/ui-components';
import { useState } from 'react';

import ToolbarPanel from '../components/ToolbarPanel';
import { MAX_DISTANCE_OFFSET_CM } from './useSupportPlaneCalibration';

const OFFSET_STEP_CM = 0.1;

type DistanceOffsetButtonProps = {
	/** Detected camera-to-support-plane distance along the optical axis. */
	cameraDistanceCm: number;
	offsetCm: number;
	onApply: (offsetCm: number, onSuccess: () => void) => void;
	isPending: boolean;
	error: Error | null;
};

// Parses the typed offset; null while it is not a valid offset.
// Accepts both "." and "," so the decimal separator does not depend on locale.
const parseOffsetCm = (draft: string): number | null => {
	const normalized = draft.trim().replace(',', '.');
	if (normalized === '') {
		return null;
	}
	const offsetCm = Math.round(Number(normalized) * 10) / 10;
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

function DistanceOffsetButton({
	cameraDistanceCm,
	offsetCm,
	onApply,
	isPending,
	error,
}: DistanceOffsetButtonProps) {
	const [open, setOpen] = useState(false);
	// Text input so it always shows "0.0", regardless of the browser locale
	const [draft, setDraft] = useState('');
	const draftOffsetCm = parseOffsetCm(draft);
	const isDraftInvalid = draft.trim() !== '' && draftOffsetCm === null;

	const apply = (value: number) => {
		onApply(value, () => setOpen(false));
	};

	const step = (direction: 1 | -1) => {
		const current = draftOffsetCm ?? offsetCm;
		const next = clampOffsetCm(
			Math.round((current + direction * OFFSET_STEP_CM) * 10) / 10,
		);
		setDraft(next.toFixed(1));
	};

	return (
		<ToolbarPanel
			label="Distance offset"
			icon={SettingsIcon}
			open={open}
			onOpenChange={(nextOpen) => {
				// Start from the applied offset each time the panel opens
				if (nextOpen) {
					setDraft(offsetCm.toFixed(1));
				}
				setOpen(nextOpen);
			}}
		>
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
								label="−"
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
							size="label"
							color="error"
							text={`Enter a number from ${RANGE_TEXT}.`}
						/>
					) : (
						<SubLabel text={`Allowed range: ${RANGE_TEXT}.`} />
					)}
				</div>
				<div className="flex items-center justify-between gap-2">
					<Label text="Corrected distance" color="normal" />
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
		</ToolbarPanel>
	);
}

export default DistanceOffsetButton;
