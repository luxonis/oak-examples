import {
	AddIcon,
	Button,
	Flex,
	Input,
	Label,
	MinusIcon,
	Popover,
	PopoverContent,
	PopoverTrigger,
	SettingsIcon,
	StyledText,
	SubHeader,
	SubLabel,
} from '@luxonis/common-fe-components';
import { useState } from 'react';

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
		<Popover
			open={open}
			onOpenChange={(nextOpen) => {
				// Start from the applied offset each time the popover opens
				if (nextOpen) {
					setDraft(offsetCm.toFixed(1));
				}
				setOpen(nextOpen);
			}}
		>
			<PopoverTrigger asChild>
				<Button
					type="button"
					variant={open ? 'filled' : 'outline'}
					icon={SettingsIcon}
					label="Distance correction"
				/>
			</PopoverTrigger>
			<PopoverContent align="end" width="xs">
				<form
					onSubmit={(event) => {
						event.preventDefault();
						if (draftOffsetCm !== null) {
							apply(draftOffsetCm);
						}
					}}
				>
					<Flex direction="column" gap="sm" width="full">
						<SubHeader text="Distance correction" />
						<Flex justifyContent="space-between" alignItems="center">
							<Label text="Detected distance" color="normal" />
							<Label text={`${cameraDistanceCm.toFixed(1)} cm`} />
						</Flex>
						<Flex direction="column" gap="xs">
							<SubLabel
								text={
									<>
										<strong>How to measure:</strong> Measure from the camera to
										the support plane along the camera’s viewing direction.
									</>
								}
							/>
							<SubLabel text="Offset = measured distance − detected distance." />
							<SubLabel text="Positive values move the support plane farther away." />
						</Flex>
						<Flex direction="column" gap="xs">
							<Flex justifyContent="space-between" alignItems="center" gap="sm">
								<Label text="Offset (cm)" color="normal" />
								<Flex alignItems="center" gap="xs">
									<Button
										type="button"
										variant="outline"
										icon={MinusIcon}
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
										textAlign="center"
										wrapperProps={{
											style: { width: '4.5rem' },
										}}
									/>
									<Button
										type="button"
										variant="outline"
										icon={AddIcon}
										label={null}
										aria-label="Increase offset"
										disabled={isPending}
										onClick={() => step(1)}
									/>
								</Flex>
							</Flex>
							<SubLabel
								text={`Allowed range: −${MAX_DISTANCE_OFFSET_CM} to +${MAX_DISTANCE_OFFSET_CM} cm.`}
							/>
						</Flex>
						<Flex justifyContent="space-between" alignItems="center">
							<Label text="Corrected distance" color="normal" />
							<Label
								weight="bold"
								text={
									draftOffsetCm === null
										? '–'
										: `${(cameraDistanceCm + draftOffsetCm).toFixed(1)} cm`
								}
							/>
						</Flex>
						{error ? (
							<StyledText size="label" color="error" text={error.message} />
						) : null}
						<Flex gap="sm" justifyContent="flex-end">
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
									isPending ||
									draftOffsetCm === null ||
									draftOffsetCm === offsetCm
								}
							/>
						</Flex>
					</Flex>
				</form>
			</PopoverContent>
		</Popover>
	);
}

export default DistanceOffsetButton;
