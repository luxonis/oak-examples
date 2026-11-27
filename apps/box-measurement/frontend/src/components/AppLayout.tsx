import { Label } from '@luxonis/ui-components';
import type { ReactNode } from 'react';
import { AppShell } from '../AppShell';

type AppLayoutProps = {
	stream: ReactNode;
	controls: ReactNode;
};

function AppLayout({ stream, controls }: AppLayoutProps) {
	return (
		<AppShell title="Box Measurement" streams={stream}>
			<Label text="Measures the length, width, height and volume of boxes resting on a flat support plane, such as a conveyor belt." />
			{controls}
		</AppShell>
	);
}

export default AppLayout;
