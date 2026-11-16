import {
	Alert,
	Button,
	Card,
	Flex,
	Header,
	Label,
	NormalText,
	SubLabel,
	Switch,
} from '@luxonis/ui-components';
import { useState } from 'react';

interface DistanceDisplayProps {
	distance: number | null;
	stdDeviation?: number | null;
	pointCount?: number;
	hasInvalidDepth?: boolean;
	trackingEnabled?: boolean;
	onToggleTracking?: () => void;
	onClear: () => void;
}

type UnitSystem = 'metric' | 'imperial';
type Rounding = 1 | 2 | 3 | 4;

type Choice<T> = { value: T; label: string };

const unitOptions: Choice<UnitSystem>[] = [
	{ value: 'metric', label: 'Metric' },
	{ value: 'imperial', label: 'Imperial' },
];

const roundingOptions: Choice<Rounding>[] = [1, 2, 3, 4].map((value) => ({
	value: value as Rounding,
	label: String(value),
}));

export function DistanceDisplay({
	distance,
	stdDeviation,
	pointCount = 0,
	hasInvalidDepth = false,
	trackingEnabled = true,
	onToggleTracking,
	onClear,
}: DistanceDisplayProps) {
	const [unitSystem, setUnitSystem] = useState<UnitSystem>('metric');
	const [rounding, setRounding] = useState<Rounding>(3);

	const formatDistance = (dist: number) => {
		if (unitSystem === 'metric') {
			if (dist < 0.01) {
				return `${(dist * 1000).toFixed(rounding === 1 ? 0 : rounding - 1)} mm`;
			}

			if (dist < 1) {
				return `${(dist * 100).toFixed(rounding === 1 ? 0 : rounding - 1)} cm`;
			}

			return `${dist.toFixed(rounding)} m`;
		}

		const feet = dist * 3.28084;
		if (feet < 1) {
			return `${(feet * 12).toFixed(rounding === 1 ? 0 : rounding - 1)} in`;
		}

		if (feet < 5280) {
			return `${feet.toFixed(rounding)} ft`;
		}

		return `${(feet / 5280).toFixed(rounding)} mi`;
	};

	return (
		<>
			<Card title="Measurement" variant="outline" intent="white">
				<Flex direction="column" gap="sm">
					{distance !== null ? (
						<Flex direction="column" gap="xs">
							<p className="flex flex-wrap items-baseline gap-x-2 tabular-nums">
								<Header text={formatDistance(distance)} color="success" />
								{stdDeviation !== null &&
								stdDeviation !== undefined &&
								stdDeviation > 0 ? (
									<Label text={`± ${formatDistance(stdDeviation)}`} />
								) : null}
							</p>
							<SubLabel text="3D Euclidean distance" />
						</Flex>
					) : pointCount === 2 ? (
						<Flex direction="column" gap="xs">
							<NormalText text="Calculating distance..." />
							<SubLabel text="Two points selected" />
						</Flex>
					) : (
						<Label text="Select two points to measure" />
					)}

					{hasInvalidDepth && (distance !== null || pointCount === 2) ? (
						<Alert
							intent="warning"
							description="Invalid depth detected. Try selecting different points."
						/>
					) : null}

					{onToggleTracking ? (
						<Flex direction="row" align="center" justify="between" gap="sm">
							<Flex direction="column">
								<Label id="tracking-label" text="Track points" />
								<SubLabel text="Points follow the target as it moves." />
							</Flex>
							<Switch
								aria-labelledby="tracking-label"
								value={trackingEnabled}
								onChange={onToggleTracking}
								showActiveLabelOnly
							/>
						</Flex>
					) : null}

					<Button
						variant="outline"
						intent="gray"
						onClick={onClear}
						disabled={pointCount === 0}
					>
						Clear points
					</Button>
				</Flex>
			</Card>

			<Card title="Display" variant="outline" intent="white">
				<Flex direction="column" gap="sm">
					<ChoiceGroup
						legend="Units"
						options={unitOptions}
						selected={unitSystem}
						onSelect={setUnitSystem}
						className="grid grid-cols-2 gap-2"
					/>
					<ChoiceGroup
						legend="Decimal places"
						options={roundingOptions}
						selected={rounding}
						onSelect={setRounding}
						className="grid grid-cols-4 gap-2"
					/>
				</Flex>
			</Card>
		</>
	);
}

function ChoiceGroup<T extends string | number>({
	legend,
	options,
	selected,
	onSelect,
	className,
}: {
	legend: string;
	options: Choice<T>[];
	selected: T;
	onSelect: (value: T) => void;
	className: string;
}) {
	return (
		<fieldset className="flex flex-col gap-1">
			<legend>
				<Label text={legend} />
			</legend>
			<div className={className}>
				{options.map(({ value, label }) => {
					const isSelected = value === selected;
					return (
						<Button
							key={value}
							variant={isSelected ? 'filled' : 'outline'}
							intent={isSelected ? 'active' : 'gray'}
							aria-pressed={isSelected}
							onClick={() => onSelect(value)}
						>
							{label}
						</Button>
					);
				})}
			</div>
		</fieldset>
	);
}
