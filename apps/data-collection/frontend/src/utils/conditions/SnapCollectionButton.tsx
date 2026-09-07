import { Button } from '@luxonis/ui-components';

interface SnapActionButtonProps {
	running: boolean;
	busy: boolean;
	disabled?: boolean;
	onClick: () => void;
}

export function SnapCollectionButton({
	running,
	busy,
	disabled,
	onClick,
}: SnapActionButtonProps) {
	return (
		<Button
			className="w-full font-semibold"
			intent={running ? 'error' : 'active'}
			onClick={onClick}
			disabled={disabled}
		>
			{busy
				? running
					? 'Stopping...'
					: 'Starting...'
				: running
					? 'Stop Snapping'
					: 'Start Snapping'}
		</Button>
	);
}
