import { Streams, useDaiConnection } from '@luxonis/depthai-viewer-common';
import { MessageInput } from './MessageInput.tsx';

function App() {
	const connection = useDaiConnection();

	return (
		<main className="flex h-screen w-screen flex-col items-center gap-4 p-4 text-center">
			<h1 className="text-2xl font-bold">
				Local Frontend for Visualizer Example
			</h1>

			<Streams hideToolbar />

			{connection.connected && <MessageInput />}
		</main>
	);
}

export default App;
