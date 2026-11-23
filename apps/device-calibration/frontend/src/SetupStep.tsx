import { Streams, useDaiConnection } from '@luxonis/depthai-viewer-common';
import {
	Alert,
	Button,
	Input,
	ModalContent,
	ModalContextAware,
	ModalFooter,
	ModalHeader,
	Select,
	Switch,
	useNewMultiModalContext,
} from '@luxonis/ui-components';
import { Fragment, useEffect, useState } from 'react';
import {
	type Act,
	type BoardCamera,
	type BoardConfig,
	type CalibrationState,
	type Charuco,
	type StepProps,
	callService,
} from './api.ts';
import { Field, Section } from './ui.tsx';

const MODELS = ['perspective', 'fisheye'].map((value) => ({
	value,
	component: value,
}));

export function Main({ state, act }: StepProps) {
	return (
		<>
			<div className="relative min-h-0 flex-[2] overflow-hidden">
				<Streams defaultTopics={['Camera']} allowedTopics={['Camera']} />
			</div>
			<div className="min-h-0 flex-[3] overflow-y-auto">
				<BoardTable
					key={`${state.board.name}-${state.boardSource}`}
					board={state.board}
					act={act}
				/>
			</div>
		</>
	);
}

/** Text inputs commit on blur: the backend echoes the board back, which would fight typing. */
function BoardTable({ board, act }: { board: BoardConfig; act: Act }) {
	const edit = (socket: string, patch: Partial<BoardCamera>) =>
		act('set_board', {
			board: {
				...board,
				cameras: {
					...board.cameras,
					[socket]: { ...board.cameras[socket], ...patch },
				},
			},
		});
	const sockets = Object.keys(board.cameras);
	const toCam = sockets.map((value) => ({ value, component: value }));
	const num = (value: string, apply: (v: number) => void) =>
		value !== '' && apply(Number(value));

	return (
		<table className="w-full text-sm">
			<thead>
				<tr className="text-left text-muted-foreground">
					<th className="font-normal">On</th>
					<th className="font-normal">Socket</th>
					<th className="font-normal">Name</th>
					<th className="font-normal">Model</th>
					<th className="font-normal">To camera</th>
				</tr>
			</thead>
			<tbody>
				{sockets.map((socket) => {
					const cam = board.cameras[socket];
					const ext = cam.extrinsics;
					const setExt = (patch: Partial<NonNullable<typeof ext>>) =>
						ext && edit(socket, { extrinsics: { ...ext, ...patch } });
					return (
						<Fragment key={socket}>
							<tr className="border-t border-border">
								<td className="pt-2">
									<Switch
										value={cam.enabled}
										onChange={(enabled) => edit(socket, { enabled })}
										showActiveLabelOnly
									/>
								</td>
								<td className="px-3 pt-2">
									<div>{socket}</div>
									<div className="text-muted-foreground">{cam.type}</div>
								</td>
								<td className="pt-2 pr-2">
									<Input
										defaultValue={cam.name}
										onBlur={(e) => edit(socket, { name: e.target.value })}
									/>
								</td>
								<td className="pt-2 pr-2">
									<Select
										items={MODELS}
										value={cam.model}
										onChange={(model) =>
											edit(socket, { model: model as BoardCamera['model'] })
										}
									/>
								</td>
								<td className="pt-2">
									{ext && (
										<Select
											items={toCam.filter((s) => s.value !== socket)}
											value={ext.to_cam}
											onChange={(to_cam) => setExt({ to_cam })}
										/>
									)}
								</td>
							</tr>
							<tr>
								<td />
								<td colSpan={4} className="pb-2 text-muted-foreground">
									<p className="mb-1">
										{cam.sensorName} {cam.size[0]} x {cam.size[1]}
									</p>
									<div className="grid grid-cols-5 gap-2">
										<Field label="HFOV (deg)">
											<Input
												type="number"
												defaultValue={cam.hfov}
												onBlur={(e) =>
													num(e.target.value, (hfov) => edit(socket, { hfov }))
												}
											/>
										</Field>
										{ext &&
											(['x', 'y', 'z'] as const).map((axis) => (
												<Field key={axis} label={`${axis} cm`}>
													<Input
														type="number"
														defaultValue={ext.specTranslation[axis]}
														onBlur={(e) =>
															num(e.target.value, (v) =>
																setExt({
																	specTranslation: {
																		...ext.specTranslation,
																		[axis]: v,
																	},
																}),
															)
														}
													/>
												</Field>
											))}
										{cam.hasAutofocus && (
											<Field label="Lens">
												<Input
													type="number"
													defaultValue={cam.lensPosition}
													onBlur={(e) =>
														num(e.target.value, (lensPosition) =>
															edit(socket, { lensPosition }),
														)
													}
												/>
											</Field>
										)}
									</div>
								</td>
							</tr>
						</Fragment>
					);
				})}
			</tbody>
		</table>
	);
}

export function Side({ state, act }: StepProps) {
	const { board, boardProblems } = state;
	const modal = useNewMultiModalContext<{ charuco: Record<string, never> }>();
	const items = state.boardNames.map((value) => ({ value, component: value }));
	return (
		<>
			<Section title="Board config">
				{board.name ? (
					<p className="text-sm">
						{board.name}{' '}
						<span className="text-muted-foreground">({state.boardSource})</span>
					</p>
				) : (
					<Alert
						variant="light"
						intent="warning"
						title="No board config detected"
						description="Pick one."
					/>
				)}
				<Select
					items={items}
					value={board.name || undefined}
					placeholder="Pick a board config"
					onChange={(name) => act('select_board', { name })}
				/>
				{boardProblems.map((p) => (
					<p key={p} className="text-sm text-destructive">
						{p}
					</p>
				))}
			</Section>
			<Button
				onClick={() => modal.open('charuco', {})}
				disabled={
					boardProblems.length > 0 || !Object.keys(board.cameras).length
				}
			>
				Run calibration
			</Button>
			{state.imu && (
				<Button variant="link" onClick={() => act('skip_cameras')}>
					Skip to IMU
				</Button>
			)}
			<ModalContextAware context={modal} which="charuco">
				{(_, close) => (
					<ModalContent maxWidth="56rem" aria-describedby={undefined}>
						<BoardDialog state={state} act={act} close={close} />
					</ModalContent>
				)}
			</ModalContextAware>
		</>
	);
}

type Preview = { png?: string; error?: string };

const SIZE_FIELDS = [
	['squaresX', 'Squares X'],
	['squaresY', 'Squares Y'],
	['squareCm', 'Square size (cm)'],
	['markerCm', 'Marker size (cm)'],
] as const;

function BoardDialog({
	state,
	act,
	close,
}: { state: CalibrationState; act: Act; close: () => void }) {
	const { daiConnection } = useDaiConnection();
	const last = state.lastCharuco;
	const [form, setForm] = useState({
		squaresX: String(last?.squaresX ?? ''),
		squaresY: String(last?.squaresY ?? ''),
		squareCm: String(last?.squareCm ?? ''),
		markerCm: String(last?.markerCm ?? ''),
		dictionary: last?.dictionary ?? 'DICT_4X4_1000',
	});
	const [boardFixed, setBoardFixed] = useState(false);
	const [preview, setPreview] = useState<Preview | null>(null);

	const spec: Charuco = {
		...form,
		squaresX: Number(form.squaresX),
		squaresY: Number(form.squaresY),
		squareCm: Number(form.squareCm),
		markerCm: Number(form.markerCm),
	};
	const filled = SIZE_FIELDS.every(([key]) => spec[key] > 0);
	const specKey = JSON.stringify(spec);

	// Debounced preview; a late reply for an older spec is dropped.
	// biome-ignore lint/correctness/useExhaustiveDependencies: specKey stands for spec
	useEffect(() => {
		setPreview(null);
		if (!filled) return;
		let stale = false;
		const id = window.setTimeout(
			() =>
				callService<Preview>(
					daiConnection,
					'Board Preview',
					{ ...spec },
					(p) => {
						if (!stale) setPreview(p);
					},
				),
			200,
		);
		return () => {
			stale = true;
			window.clearTimeout(id);
		};
	}, [specKey, filled, daiConnection]);

	const start = () => {
		act('start_capture', { charuco: { ...spec }, boardFixed });
		close();
	};

	return (
		<>
			<ModalHeader title="ChArUco board" />
			<div className="grid grid-cols-2 gap-6">
				<div className="flex flex-col gap-3">
					{SIZE_FIELDS.map(([key, label]) => (
						<Field key={key} label={label}>
							<Input
								type="number"
								min={0}
								step={key.endsWith('Cm') ? 0.1 : 1}
								value={form[key]}
								onChange={(e) => setForm({ ...form, [key]: e.target.value })}
							/>
						</Field>
					))}
					<Field label="Dictionary">
						<Select
							items={state.dictionaries.map((value) => ({
								value,
								component: value,
							}))}
							value={form.dictionary}
							onChange={(dictionary) => setForm({ ...form, dictionary })}
						/>
					</Field>
					<span className="flex items-center gap-2 text-sm">
						Board is fixed, I move the device
						<Switch
							value={boardFixed}
							onChange={setBoardFixed}
							showActiveLabelOnly
						/>
					</span>
				</div>
				<div className="flex flex-col gap-2">
					{preview?.png ? (
						<img
							src={`data:image/png;base64,${preview.png}`}
							alt="ChArUco board preview"
							className="w-full rounded-md border border-border"
						/>
					) : (
						<div className="flex aspect-[4/3] items-center justify-center rounded-md border border-border bg-muted text-sm text-muted-foreground">
							Board preview
						</div>
					)}
					{filled && (
						<p className="text-sm text-muted-foreground">
							{spec.squaresX} x {spec.squaresY} squares,{' '}
							{(spec.squaresX * spec.squareCm).toFixed(1)} x{' '}
							{(spec.squaresY * spec.squareCm).toFixed(1)} cm
						</p>
					)}
					{preview?.error && (
						<p className="text-sm text-destructive">{preview.error}</p>
					)}
				</div>
			</div>
			<ModalFooter>
				<Button variant="outline" onClick={close}>
					Cancel
				</Button>
				<Button onClick={start} disabled={!filled || !!preview?.error}>
					Start capture
				</Button>
			</ModalFooter>
		</>
	);
}
