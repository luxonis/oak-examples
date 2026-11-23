import type { ComponentType } from 'react';
import * as Capture from './CaptureStep.tsx';
import * as Imu from './ImuStep.tsx';
import * as Results from './ResultsStep.tsx';
import * as Setup from './SetupStep.tsx';
import type { Phase, StepProps } from './api.ts';
import { DeviceSidebar, StepList } from './ui.tsx';
import { useCalibration } from './useCalibration.ts';

// Main area and right-sidebar content for each phase.
const VIEWS: Record<
	Phase,
	[ComponentType<StepProps>, ComponentType<StepProps>]
> = {
	setup: [Setup.Main, Setup.Side],
	capture: [Capture.Main, Capture.Side],
	processing: [Capture.ProcessingMain, Capture.ProcessingSide],
	results: [Results.Main, Results.Side],
	imu: [Imu.Main, Imu.Side],
	review: [Imu.Main, Imu.ReviewSide],
};

function App() {
	const { state, rows, act, connected } = useCalibration();

	if (!state) {
		return (
			<main className="flex h-screen w-screen items-center justify-center text-sm text-muted-foreground">
				{connected ? 'Waiting for the device...' : 'Connecting...'}
			</main>
		);
	}

	const [Main, Side] = VIEWS[state.phase];
	const props = { state, rows, act };
	return (
		<main className="flex h-screen w-screen flex-row gap-6 p-6">
			<aside className="flex max-h-full w-[280px] shrink-0 flex-col gap-5 overflow-y-auto pr-2 text-left">
				<StepList phase={state.phase} />
				<DeviceSidebar device={state.device} />
			</aside>

			<div className="w-0.5 shrink-0 bg-border" />

			<div className="flex min-w-0 flex-1 flex-col gap-4">
				<Main {...props} />
			</div>

			<div className="w-0.5 shrink-0 bg-border" />

			<aside className="flex max-h-full w-[380px] shrink-0 flex-col gap-5 overflow-y-auto pr-2 text-left">
				<h1 className="text-2xl font-bold">Device Calibration</h1>
				<p className="text-sm text-muted-foreground">
					Calibrate the cameras and the IMU in one guided flow. Nothing is
					written to the device until you press Flash.
				</p>

				<Side {...props} />

				<div
					className={`mt-auto flex items-center gap-2 border-t border-border pt-4 text-sm ${
						connected ? 'text-success' : 'text-destructive'
					}`}
				>
					<div
						className={`h-3 w-3 rounded-full ${
							connected ? 'bg-success' : 'bg-destructive'
						}`}
					/>
					<span>{connected ? 'Connected to device' : 'Disconnected'}</span>
				</div>
			</aside>
		</main>
	);
}

export default App;
