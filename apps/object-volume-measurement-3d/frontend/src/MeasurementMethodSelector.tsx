import { useDaiConnection } from '@luxonis/depthai-viewer-common';
import { Button, Label } from '@luxonis/ui-components';
import { useState } from 'react';
import { postToObjectVolumeService } from './services.ts';

export type MeasurementMethod = 'obb' | 'heightgrid';

const METHODS: { id: MeasurementMethod; label: string }[] = [
	{ id: 'obb', label: 'Bounding box' },
	{ id: 'heightgrid', label: 'Height grid' },
];

const DESCRIPTIONS: Record<MeasurementMethod, string[]> = {
	obb: [
		'Minimal 3D box that encloses the segmented object.',
		'Volume is computed as L x W x H of the box.',
		"Provides a fast upper bound on the object's volume.",
	],
	heightgrid: [
		'Requires the object to rest on a flat surface (e.g. desk or floor).',
		"Builds a height grid over the object's footprint on the support plane. Total volume is the sum of the grid cell volumes.",
		'Dimensions are still shown as a box (L, W, H), but the volume comes from the height grid integration.',
		'More accurate for irregular shapes, but sensitive to errors in plane fitting.',
	],
};

export function MeasurementMethodSelector() {
	const connection = useDaiConnection();
	const [method, setMethod] = useState<MeasurementMethod>('obb');

	const handleClick = (next: MeasurementMethod) => {
		if (!connection.connected) return;

		setMethod(next);
		postToObjectVolumeService(
			connection.daiConnection,
			'Measurement Method Service',
			{ method: next },
		);
	};

	return (
		<fieldset className="flex flex-col gap-1">
			<legend>
				<Label text="Measurement method" />
			</legend>
			<div className="grid grid-cols-2 gap-2">
				{METHODS.map(({ id, label }) => {
					const isActive = id === method;

					return (
						<Button
							key={id}
							variant={isActive ? 'filled' : 'outline'}
							intent={isActive ? 'active' : 'gray'}
							aria-pressed={isActive}
							disabled={!connection.connected}
							onClick={() => {
								if (!isActive) handleClick(id);
							}}
						>
							{label}
						</Button>
					);
				})}
			</div>

			<ul className="ovm-notes">
				{DESCRIPTIONS[method].map((line) => (
					<li key={line}>
						<Label text={line} />
					</li>
				))}
			</ul>

			{method === 'heightgrid' ? (
				<Button
					variant="outline"
					intent="gray"
					disabled={!connection.connected}
					onClick={() => handleClick('heightgrid')}
				>
					Retry plane capture
				</Button>
			) : null}
		</fieldset>
	);
}
