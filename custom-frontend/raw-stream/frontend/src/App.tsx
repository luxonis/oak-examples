import { Streams } from '@luxonis/depthai-viewer-common';
import { AppShell } from './AppShell.tsx';
import { MessageInput } from './MessageInput.tsx';

function App() {
	return (
		<AppShell title="Raw Stream" streams={<Streams hideToolbar />}>
			<MessageInput />
		</AppShell>
	);
}

export default App;
