import { useDaiConnection } from '@luxonis/depthai-viewer-common';
import { useToast } from '@luxonis/ui-components';
import { useEffect, useState } from 'react';
import { postToDataCollectionService } from '../../services.ts';
import { SliderControl } from '../SliderControl.tsx';
import { ConditionCard } from './ConditionCard.tsx';
import { CooldownMinutesInput } from './CooldownMinutesInput.tsx';
import { EdgeBufferPercentInput } from './EdgeBufferPercentInput.tsx';
import { SnapCollectionButton } from './SnapCollectionButton.tsx';

interface SnappingConfig {
	running: boolean;
	timed: { enabled: boolean; cooldown: number };
	noDetections: { enabled: boolean; cooldown: number };
	lowConfidence: { enabled: boolean; threshold: number; cooldown: number };
	lostMid: { enabled: boolean; cooldown: number; margin: number };
}

interface SnapConditionsPanelProps {
	initialConfig?: SnappingConfig;
}

export function SnapConditionsPanel({
	initialConfig,
}: SnapConditionsPanelProps) {
	const connection = useDaiConnection();
	const { toast } = useToast();

	const [running, setRunning] = useState(false);
	const [busy, setBusy] = useState(false);

	const hasTooManyDecimals = (value: string) => /\.\d{2,}$/.test(value.trim());
	const oneDecimalOrInt = (value: string) =>
		/^\d+(\.\d{0,1})?$/.test(value.trim());
	const asFloat = (value: string) => Number.parseFloat(value.trim());

	const [timingEnabled, setTimingEnabled] = useState(false);
	const [timingStr, setTimingStr] = useState('5.0');
	const timingMin = asFloat(timingStr);
	const timingValid =
		!timingEnabled ||
		(timingStr !== '' &&
			oneDecimalOrInt(timingStr) &&
			Number.isFinite(timingMin) &&
			timingMin > 0);

	const [noDetEnabled, setNoDetEnabled] = useState(false);
	const [noDetStr, setNoDetStr] = useState('5.0');
	const noDetMin = asFloat(noDetStr);
	const noDetValid =
		!noDetEnabled ||
		(noDetStr !== '' &&
			oneDecimalOrInt(noDetStr) &&
			Number.isFinite(noDetMin) &&
			noDetMin >= 0);

	const [lowConfEnabled, setLowConfEnabled] = useState(false);
	const [lowConfStr, setLowConfStr] = useState('5.0');
	const lowConfMin = asFloat(lowConfStr);
	const lowConfValid =
		!lowConfEnabled ||
		(lowConfStr !== '' &&
			oneDecimalOrInt(lowConfStr) &&
			Number.isFinite(lowConfMin) &&
			lowConfMin >= 0);
	const [lowConfThreshold, setLowConfThreshold] = useState(0.3);

	const [lostMidEnabled, setLostMidEnabled] = useState(false);
	const [lostMidStr, setLostMidStr] = useState('5.0');
	const lostMidMin = asFloat(lostMidStr);
	const lostMidValid =
		!lostMidEnabled ||
		(lostMidStr !== '' &&
			oneDecimalOrInt(lostMidStr) &&
			Number.isFinite(lostMidMin) &&
			lostMidMin >= 0);

	const [lostMidPctStr, setLostMidPctStr] = useState('20');
	const lostMidPct = Number.parseFloat(lostMidPctStr);
	const lostMidPctValid =
		Number.isFinite(lostMidPct) && lostMidPct >= 0 && lostMidPct <= 49;

	const anyInvalid =
		!timingValid ||
		!noDetValid ||
		!lowConfValid ||
		!lostMidValid ||
		!lostMidPctValid;
	const disabledControls = busy || running;

	useEffect(() => {
		if (!initialConfig) {
			console.log('[SnapConditionsPanel] No initialConfig provided');
			return;
		}

		console.log(
			'[SnapConditionsPanel] Restoring config from backend:',
			initialConfig,
		);
		setRunning(initialConfig.running);

		if (initialConfig.timed) {
			setTimingEnabled(initialConfig.timed.enabled);
			if (initialConfig.timed.cooldown > 0) {
				setTimingStr(initialConfig.timed.cooldown.toFixed(1));
			}
		}

		if (initialConfig.noDetections) {
			setNoDetEnabled(initialConfig.noDetections.enabled);
			if (initialConfig.noDetections.cooldown > 0) {
				setNoDetStr(initialConfig.noDetections.cooldown.toFixed(1));
			}
		}

		if (initialConfig.lowConfidence) {
			setLowConfEnabled(initialConfig.lowConfidence.enabled);
			setLowConfThreshold(initialConfig.lowConfidence.threshold);
			if (initialConfig.lowConfidence.cooldown > 0) {
				setLowConfStr(initialConfig.lowConfidence.cooldown.toFixed(1));
			}
		}

		if (initialConfig.lostMid) {
			setLostMidEnabled(initialConfig.lostMid.enabled);
			if (initialConfig.lostMid.cooldown > 0) {
				setLostMidStr(initialConfig.lostMid.cooldown.toFixed(1));
			}
			setLostMidPctStr(
				Math.round(initialConfig.lostMid.margin * 100).toString(),
			);
		}
	}, [initialConfig]);

	const warnIfTooManyDecimals = (label: string, value: string) => {
		if (value.trim() !== '' && hasTooManyDecimals(value)) {
			toast({
				description: `${label} allows at most one decimal place.`,
				colorVariant: 'warning',
			});
		}
	};

	const postToService = (
		payload: Record<string, unknown>,
		onDone?: () => void,
	) => {
		postToDataCollectionService(
			connection.daiConnection,
			'Snap Collection Service',
			payload,
			() => {
				onDone?.();
			},
		);
	};

	const postConfig = (runFlag: boolean) => {
		const marginFrac = Math.max(0, Math.min(49, lostMidPct || 0)) / 100;

		const payload = runFlag
			? {
					timed: {
						enabled: timingEnabled,
						cooldown: timingEnabled ? timingMin * 60 : 0,
					},
					noDetections: {
						enabled: noDetEnabled,
						cooldown: noDetEnabled ? noDetMin * 60 : undefined,
					},
					lowConfidence: lowConfEnabled
						? {
								enabled: true,
								threshold: lowConfThreshold,
								cooldown: lowConfMin * 60,
							}
						: { enabled: false },
					lostMid: lostMidEnabled
						? {
								enabled: true,
								cooldown: lostMidMin * 60,
								margin: marginFrac,
							}
						: { enabled: false },
				}
			: {
					timed: { enabled: false },
					noDetections: { enabled: false },
					lowConfidence: { enabled: false },
					lostMid: { enabled: false },
				};

		postToService(payload, () => {
			setBusy(false);
			setRunning(runFlag);
			toast({
				description: runFlag ? 'Snapping started.' : 'Snapping stopped.',
				colorVariant: 'success',
			});
		});
	};

	const pushLowConfUpdate = () => {
		if (!connection.connected || !running || !lowConfEnabled || !lowConfValid) {
			return;
		}
		postToService({
			lowConfidence: {
				enabled: true,
				threshold: lowConfThreshold,
				cooldown: lowConfMin * 60,
			},
		});
	};

	const pushLostMidUpdate = () => {
		if (
			!connection.connected ||
			!running ||
			!lostMidEnabled ||
			!lostMidValid ||
			!lostMidPctValid
		) {
			return;
		}
		const marginFrac = Math.max(0, Math.min(49, lostMidPct || 0)) / 100;
		postToService({
			lostMid: {
				enabled: true,
				cooldown: lostMidMin * 60,
				margin: marginFrac,
			},
		});
	};

	const handleStartStop = () => {
		if (!connection.connected) {
			toast({
				description: 'Not connected to device.',
				colorVariant: 'error',
			});
			return;
		}
		if (busy) return;

		if (!running) {
			if (timingEnabled && !timingValid) {
				toast({
					description:
						'Please enter a positive timing cooldown (minutes, max 1 decimal).',
					colorVariant: 'error',
				});
				return;
			}
			if (noDetEnabled && !noDetValid) {
				toast({
					description:
						'Please enter a non-negative no-detections cooldown (minutes, max 1 decimal).',
					colorVariant: 'error',
				});
				return;
			}
			if (lowConfEnabled) {
				if (!lowConfValid) {
					toast({
						description:
							'Please enter a non-negative low-confidence cooldown (minutes, max 1 decimal).',
						colorVariant: 'error',
					});
					return;
				}
				if (!(lowConfThreshold >= 0 && lowConfThreshold <= 1)) {
					toast({
						description: 'Confidence threshold must be between 0.00 and 1.00.',
						colorVariant: 'error',
					});
					return;
				}
			}
			if (lostMidEnabled) {
				if (!lostMidValid) {
					toast({
						description:
							'Please enter a non-negative lost-in-middle cooldown (minutes, max 1 decimal).',
						colorVariant: 'error',
					});
					return;
				}
				if (!lostMidPctValid) {
					toast({
						description: 'Edge buffer must be between 0% and 49%.',
						colorVariant: 'error',
					});
					return;
				}
			}
		}

		setBusy(true);
		toast({
			description: !running ? 'Starting snapping...' : 'Stopping snapping...',
			colorVariant: 'gray',
		});
		postConfig(!running);
	};

	return (
		<div className="flex flex-col gap-4">
			<ConditionCard
				title="Timing"
				enabled={timingEnabled}
				onToggle={setTimingEnabled}
				disabled={disabledControls}
				description="Sends a snap periodically; throttled by the cooldown."
			>
				<CooldownMinutesInput
					label="Cooldown (minutes)"
					value={timingStr}
					onChange={setTimingStr}
					onBlur={() => warnIfTooManyDecimals('Timing cooldown', timingStr)}
					valid={timingValid}
					disabled={disabledControls}
				/>
			</ConditionCard>

			<ConditionCard
				title="No detections"
				enabled={noDetEnabled}
				onToggle={setNoDetEnabled}
				disabled={disabledControls}
				description="Sends a snap when a frame has zero detections; throttled by the cooldown."
			>
				<CooldownMinutesInput
					label="Cooldown (minutes)"
					value={noDetStr}
					onChange={setNoDetStr}
					onBlur={() =>
						warnIfTooManyDecimals('No-detections cooldown', noDetStr)
					}
					valid={noDetValid}
					disabled={disabledControls}
				/>
			</ConditionCard>

			<ConditionCard
				title="Low confidence"
				enabled={lowConfEnabled}
				onToggle={setLowConfEnabled}
				disabled={disabledControls}
				description="Sends a snap if any detection confidence falls below the threshold; throttled by the cooldown."
			>
				<SliderControl
					label={`Confidence threshold: ${(lowConfThreshold * 100).toFixed(0)}%`}
					value={lowConfThreshold}
					onChange={setLowConfThreshold}
					onCommit={pushLowConfUpdate}
					min={0}
					max={1}
					step={0.01}
					disabled={disabledControls}
					aria-label="Low confidence threshold"
				/>

				<CooldownMinutesInput
					label="Cooldown (minutes)"
					value={lowConfStr}
					onChange={setLowConfStr}
					onBlur={() =>
						warnIfTooManyDecimals('Low-confidence cooldown', lowConfStr)
					}
					valid={lowConfValid}
					disabled={disabledControls}
				/>
			</ConditionCard>

			<ConditionCard
				title="Lost in middle"
				enabled={lostMidEnabled}
				onToggle={setLostMidEnabled}
				disabled={disabledControls}
				description="Sends a snap the moment a tracked object disappears inside the center area; throttled by the cooldown."
			>
				<EdgeBufferPercentInput
					value={lostMidPctStr}
					onChange={setLostMidPctStr}
					onBlur={pushLostMidUpdate}
					valid={lostMidPctValid}
					disabled={disabledControls}
				/>
				<CooldownMinutesInput
					label="Cooldown (minutes)"
					value={lostMidStr}
					onChange={setLostMidStr}
					onBlur={() => {
						if (lostMidStr.trim() !== '' && hasTooManyDecimals(lostMidStr)) {
							toast({
								description:
									'Lost-in-middle cooldown allows at most one decimal place.',
								colorVariant: 'warning',
							});
						}
						pushLostMidUpdate();
					}}
					valid={lostMidValid}
					disabled={disabledControls}
				/>
			</ConditionCard>

			<div className="mt-2">
				<SnapCollectionButton
					running={running}
					busy={busy}
					disabled={
						busy ||
						anyInvalid ||
						(!running &&
							lowConfEnabled &&
							!(lowConfThreshold >= 0 && lowConfThreshold <= 1))
					}
					onClick={handleStartStop}
				/>
			</div>
		</div>
	);
}
