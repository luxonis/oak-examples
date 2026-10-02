import { Streams, useDaiConnection } from '@luxonis/depthai-viewer-common';
import { MessageInput } from './MessageInput.tsx';

function App() {
	const connection = useDaiConnection();

	return (
		<main className="flex h-screen w-screen flex-row gap-6 p-6">
			<div className="relative min-w-0 flex-1">
				<Streams />
			</div>

			<div className="w-0.5 shrink-0 bg-border" />

			<aside className="flex max-h-full w-[380px] shrink-0 flex-col gap-6 overflow-y-auto pr-1 text-left">
				<div className="flex flex-col gap-4">
					<h1 className="text-2xl font-bold">
						Roboflow Workflow & DepthAI Integration Example
					</h1>
					<p>
						Simple application showing integration between{' '}
						<b>DepthAI cameras</b> and <b>Roboflow Workflow</b> through the
						Inference package. Live video is streamed from the camera, processed
						through your Roboflow workflow on the device, and both predictions
						and visualizations are rendered in the DepthAI Visualizer.
					</p>
					<ul className="list-disc pl-6">
						<li>
							To switch the displayed stream, click the <b>X</b> icon and select
							another source.
						</li>
						<li>
							To toggle detection overlays on or off, use the <b>filter icon</b>{' '}
							at the top.
						</li>
					</ul>
				</div>

				<MessageInput />

				<div
					className={`mt-auto flex items-center gap-2 ${connection.connected ? 'text-success' : 'text-destructive'}`}
				>
					<div
						className={`h-3 w-3 rounded-full ${connection.connected ? 'bg-success' : 'bg-destructive'}`}
					/>
					<span>
						{connection.connected ? 'Connected to device' : 'Disconnected'}
					</span>
				</div>
			</aside>
		</main>
	);
}

export default App;
