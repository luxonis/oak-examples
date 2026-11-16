import { useDaiConnection } from '@luxonis/depthai-viewer-common';
import { Header, Label } from '@luxonis/ui-components';
import type { ReactNode } from 'react';
import StatusDot from './StatusDot';

// The dot colours are the tokens behind bg-success and bg-destructive.
const CONNECTED = {
	label: 'Connected to device',
	textClass: 'text-success',
	dotColor: 'var(--lux-success)',
};
const DISCONNECTED = {
	label: 'Disconnected',
	textClass: 'text-destructive',
	dotColor: 'var(--lux-destructive)',
};

type AppLayoutProps = {
	stream: ReactNode;
	controls: ReactNode;
};

// The layout the other apps use: the stream fills the left, and a scrolling
// right panel holds the title, description, the view's controls and the
// connection indicator. Narrow screens stack the panes.
function AppLayout({ stream, controls }: AppLayoutProps) {
	const connection = useDaiConnection().connected ? CONNECTED : DISCONNECTED;

	return (
		<main className="flex h-dvh w-full flex-row gap-6 bg-background p-6 max-[800px]:h-auto max-[800px]:min-h-dvh max-[800px]:flex-col max-[800px]:gap-5 max-[800px]:p-4">
			<div className="relative min-h-0 min-w-0 flex-1 overflow-hidden max-[800px]:h-[55dvh] max-[800px]:min-h-[260px] max-[800px]:flex-none">
				{stream}
			</div>

			<div className="w-0.5 shrink-0 bg-border max-[800px]:h-0.5 max-[800px]:w-full" />

			<aside className="flex max-h-full w-[420px] shrink-0 flex-col gap-5 overflow-y-auto pr-2 text-left max-[800px]:max-h-none max-[800px]:w-full max-[800px]:overflow-visible max-[800px]:pr-0">
				<h1>
					<Header text="Box Measurement" />
				</h1>
				<Label text="Measures the length, width, height and volume of boxes resting on a flat support plane, such as a conveyor belt." />

				{controls}

				<div
					className={`mt-auto flex items-center gap-2 border-t border-border pt-4 text-sm ${connection.textClass}`}
				>
					<StatusDot color={connection.dotColor} />
					<span>{connection.label}</span>
				</div>
			</aside>
		</main>
	);
}

export default AppLayout;
