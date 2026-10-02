import { useDaiConnection } from '@luxonis/depthai-viewer-common';
import { Switch } from '@luxonis/ui-components';
import { useNotifications } from './Notifications.tsx';
import { postToDinoTrackingService } from './services.ts';

type Props = {
	enabled: boolean;
	setEnabled: (value: boolean) => void;
};

export function OutlinesToggle({ enabled, setEnabled }: Props) {
	const connection = useDaiConnection();
	const { notify } = useNotifications();

	const handleToggle = (nextEnabled: boolean) => {
		if (!connection.connected) {
			notify('Not connected to device.', { type: 'error' });
			return;
		}

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
		<div className="flex items-center justify-between gap-4">
			<h3 className="font-semibold">Outlines</h3>
			<Switch
				value={enabled}
				onChange={handleToggle}
				showActiveLabelOnly
			/>
		</div>
	);
}
