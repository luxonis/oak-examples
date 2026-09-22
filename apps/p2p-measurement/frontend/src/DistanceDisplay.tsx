import { Button } from '@luxonis/ui-components';
import { useState } from 'react';

interface DistanceDisplayProps {
	distance: number | null;
	stdDeviation?: number | null;
	pointCount?: number;
	hasInvalidDepth?: boolean;
	trackingEnabled?: boolean;
	onToggleTracking?: () => void;
}

type UnitSystem = 'metric' | 'imperial';
type Rounding = 1 | 2 | 3 | 4;

const roundingOptions: Rounding[] = [1, 2, 3, 4];

export function DistanceDisplay({
	distance,
	stdDeviation,
	pointCount = 0,
	hasInvalidDepth = false,
	trackingEnabled = true,
	onToggleTracking,
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
		<section
			className={`rounded-md border bg-background p-4 text-center shadow-sm ${
				distance !== null ? 'border-foreground' : 'border-border'
			}`}
		>
			<div className="mb-5 flex flex-wrap items-center justify-between gap-3">
				<div className="grid grid-cols-2 gap-2">
					<Button
						size="sm"
						variant={unitSystem === 'metric' ? 'filled' : 'outline'}
						intent={unitSystem === 'metric' ? 'active' : 'gray'}
						onClick={() => setUnitSystem('metric')}
					>
						Metric
					</Button>
					<Button
						size="sm"
						variant={unitSystem === 'imperial' ? 'filled' : 'outline'}
						intent={unitSystem === 'imperial' ? 'active' : 'gray'}
						onClick={() => setUnitSystem('imperial')}
					>
						Imperial
					</Button>
				</div>

				{onToggleTracking ? (
					<Button
						size="sm"
						variant={trackingEnabled ? 'filled' : 'outline'}
						intent={trackingEnabled ? 'active' : 'gray'}
						onClick={onToggleTracking}
					>
						{trackingEnabled ? 'Tracking' : 'Static'}
					</Button>
				) : null}

				<div className="grid grid-cols-4 gap-1">
					{roundingOptions.map((decimals) => (
						<Button
							key={decimals}
							className="h-8 w-8 p-0"
							size="sm"
							variant={rounding === decimals ? 'filled' : 'outline'}
							intent={rounding === decimals ? 'active' : 'gray'}
							onClick={() => setRounding(decimals)}
						>
							{decimals}
						</Button>
					))}
				</div>
			</div>

			{distance !== null ? (
				<div>
					<div className="mb-4 text-3xl font-bold text-success">
						{formatDistance(distance)}
						{stdDeviation !== null &&
						stdDeviation !== undefined &&
						stdDeviation > 0 ? (
							<span className="ml-2 text-lg font-normal text-success">
								+/- {formatDistance(stdDeviation)}
							</span>
						) : null}
					</div>
					{hasInvalidDepth ? <InvalidDepthWarning /> : null}
					<div className="text-sm text-muted-foreground">
						3D Euclidean distance
					</div>
				</div>
			) : pointCount === 2 ? (
				<div>
					<div className="mb-3 text-lg text-warning">
						Calculating distance...
					</div>
					{hasInvalidDepth ? <InvalidDepthWarning /> : null}
					<div className="text-sm text-muted-foreground">
						Two points selected
					</div>
				</div>
			) : (
				<div className="mb-4 text-base text-muted-foreground">
					Select two points to measure
				</div>
			)}
		</section>
	);
}

function InvalidDepthWarning() {
	return (
		<div className="mb-3 rounded-md border border-destructive/30 bg-destructive/10 p-2 text-sm text-destructive">
			Invalid depth detected. Try selecting different points.
		</div>
	);
}
