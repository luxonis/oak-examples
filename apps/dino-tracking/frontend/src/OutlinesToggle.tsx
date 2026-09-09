import { useDaiConnection } from '@luxonis/depthai-viewer-common';
import { Button } from '@luxonis/ui-components';
import { useNotifications } from './Notifications.tsx';
import { postToDinoTrackingService } from './services.ts';

type Props = {
	enabled: boolean;
	setEnabled: (value: boolean) => void;
};

export function OutlinesToggle({ enabled, setEnabled }: Props) {
	const connection = useDaiConnection();
	const { notify } = useNotifications();

	const handleToggle = () => {
		if (!connection.connected) {
			notify('Not connected to device.', { type: 'error' });
			return;
		}

		const nextEnabled = !enabled;

		notify(nextEnabled ? 'Enabling outlines...' : 'Hiding outlines...', {
			type: 'info',
		});

		postToDinoTrackingService(
			connection.daiConnection,
			'Outlines Trigger Service',
			{ active: nextEnabled },
			() => {
				console.log('[Outlines] BE ack:', nextEnabled);
				setEnabled(nextEnabled);
				notify(nextEnabled ? 'Outlines enabled.' : 'Outlines disabled.', {
					type: 'success',
				});
			},
		);
	};

	return (
		<div className="flex flex-col gap-3">
			<h3 className="font-semibold">Outlines</h3>

			<Button
				variant={enabled ? 'light' : 'filled'}
				intent={enabled ? 'gray' : 'active'}
				onClick={handleToggle}
			>
				{enabled ? 'Hide Outlines' : 'Draw Outlines'}
			</Button>
		</div>
	);
}
