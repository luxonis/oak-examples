import { useDaiConnection } from '@luxonis/depthai-viewer-common';
import { Button, Label } from '@luxonis/ui-components';
import { useNotifications } from './Notifications.tsx';
import { postToDinoTrackingService } from './services.ts';

type Mode = 'heatmap' | 'bbox';

type Props = {
	currentMode: Mode;
	setCurrentMode: (mode: Mode) => void;
};

const modes: { id: Mode; label: string }[] = [
	{ id: 'heatmap', label: 'Heatmap' },
	{ id: 'bbox', label: 'Bounding boxes' },
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

		const label = modes.find((entry) => entry.id === mode)?.label ?? mode;
		notify(`Switching to ${label.toLowerCase()}...`, { type: 'info' });

		postToDinoTrackingService(
			connection.daiConnection,
			'Annotation Mode Service',
			{ mode },
			() => {
				console.log('[Annotation] BE acknowledged:', mode);
				setCurrentMode(mode);
				notify(`Annotation mode set to ${label.toLowerCase()}`, {
					type: 'success',
				});
			},
		);
	};

	return (
		<fieldset className="flex flex-col gap-1">
			<legend>
				<Label text="Annotation mode" />
			</legend>
			<div className="grid grid-cols-2 gap-2">
				{modes.map(({ id, label }) => {
					const isActive = id === currentMode;

					return (
						<Button
							key={id}
							variant={isActive ? 'filled' : 'outline'}
							intent={isActive ? 'active' : 'gray'}
							aria-pressed={isActive}
							onClick={() => handleClick(id)}
						>
							{label}
						</Button>
					);
				})}
			</div>
		</fieldset>
	);
}
