import { useDaiConnection } from '@luxonis/depthai-viewer-common';
import { Button } from '@luxonis/ui-components';
import { useState } from 'react';
import { postToObjectVolumeService } from './services.ts';

export type MeasurementMethod = 'obb' | 'heightgrid';

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
		if (next === method || !connection.connected) return;

		setMethod(next);
		postToObjectVolumeService(
			connection.daiConnection,
			'Measurement Method Service',
			{ method: next },
		);
	};

	return (
		<div className="flex flex-col gap-3">
			<h3 className="font-semibold">Measurement method</h3>

			<div className="grid grid-cols-2 gap-3">
				<Button
					variant={method === 'obb' ? 'light' : 'filled'}
					intent={method === 'obb' ? 'gray' : 'active'}
					disabled={method === 'obb' || !connection.connected}
					onClick={() => handleClick('obb')}
				>
					Min OBB
				</Button>
				<Button
					variant={method === 'heightgrid' ? 'light' : 'filled'}
					intent={method === 'heightgrid' ? 'gray' : 'active'}
					disabled={method === 'heightgrid' || !connection.connected}
					onClick={() => handleClick('heightgrid')}
				>
					Height Grid
				</Button>
			</div>

			<ul className="m-0 list-disc space-y-1 pl-5 text-sm leading-6 text-muted-foreground">
				{DESCRIPTIONS[method].map((line) => (
					<li key={line}>{line}</li>
				))}
			</ul>
		</div>
	);
}
