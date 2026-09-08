import { useDaiConnection } from '@luxonis/depthai-viewer-common';
import { Button } from '@luxonis/ui-components';
import { useNotifications } from './Notifications.tsx';
import { postToDinoTrackingService } from './services.ts';

type Mode = 'heatmap' | 'bbox';

type Props = {
	currentMode: Mode;
	setCurrentMode: (mode: Mode) => void;
};

const modes: { id: Mode; label: string }[] = [
	{ id: 'heatmap', label: 'Heatmap' },
	{ id: 'bbox', label: 'BBoxes' },
];

export function AnnotationModeSelector({ currentMode, setCurrentMode }: Props) {
	const connection = useDaiConnection();
	const { notify } = useNotifications();

	const handleClick = (mode: Mode) => {
		if (mode === currentMode) return;

		if (!connection.connected) {
			notify('Not connected to device.', { type: 'error' });
			return;
		}

		notify(`Switching to "${mode}"...`, { type: 'info' });

		postToDinoTrackingService(
			connection.daiConnection,
			'Annotation Mode Service',
			{ mode },
			() => {
				console.log('[Annotation] BE acknowledged:', mode);
				setCurrentMode(mode);
				notify(`Annotation mode set to "${mode}"`, { type: 'success' });
			},
		);
	};

	return (
		<div className="flex flex-col gap-3">
			<h3 className="font-semibold">Annotation mode</h3>

			<div className="grid grid-cols-2 gap-3">
				{modes.map(({ id, label }) => {
					const isActive = id === currentMode;

					return (
						<Button
							key={id}
							variant={isActive ? 'light' : 'filled'}
							intent={isActive ? 'gray' : 'active'}
							onClick={() => handleClick(id)}
							disabled={isActive}
						>
							{label}
						</Button>
					);
				})}
			</div>
		</div>
	);
}
