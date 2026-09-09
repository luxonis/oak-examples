import { useDaiConnection } from '@luxonis/depthai-viewer-common';
import { Button, Input } from '@luxonis/ui-components';
import {
	type ChangeEvent,
	type FormEvent,
	useCallback,
	useEffect,
	useRef,
	useState,
} from 'react';
import { useNotifications } from './Notifications';
import { postToRoboflowService } from './services.ts';

const UPDATE_SERVICE = 'Roboflow Parameter Update Service';
const INTERFACE_SERVICE = 'Roboflow Workflow Interface Service';
const REFRESH_SERVICE = 'Roboflow Workflow Refresh Service';

type WorkflowParameter = {
	name: string;
	default_value: unknown;
	kind: string[] | null;
	current_value: unknown;
};

type PipelineError = {
	event_type?: string;
	error_type?: string;
	message?: string;
	context?: string;
};

type PipelineStatus = {
	running: boolean;
	error: PipelineError | null;
};

type WorkflowInterface = {
	workspace_name: string;
	workflow_id: string;
	outputs: string[];
	parameters: WorkflowParameter[];
	pipeline?: PipelineStatus;
};

type Payload = {
	api_key: string | null;
	workspace_name: string | null;
	workflow_id: string | null;
	workflow_parameters: Record<string, unknown> | null;
};

const HEALTH_POLL_MS = 4000;
const inputClassName = 'min-w-0 w-full';

function isRecord(value: unknown): value is Record<string, unknown> {
	return typeof value === 'object' && value !== null;
}

function decodeServiceResponse(data: unknown): Record<string, unknown> | null {
	if (data === null || data === undefined) return null;
	try {
		if (typeof data === 'string')
			return JSON.parse(data) as Record<string, unknown>;
		if (data instanceof ArrayBuffer || ArrayBuffer.isView(data)) {
			const view = ArrayBuffer.isView(data)
				? new Uint8Array(data.buffer, data.byteOffset, data.byteLength)
				: new Uint8Array(data);
			return JSON.parse(new TextDecoder().decode(view)) as Record<
				string,
				unknown
			>;
		}
		if (isRecord(data)) {
			if (isRecord(data.data) && typeof data.status === 'number') {
				return data.data;
			}
			return data;
		}
	} catch (err) {
		console.error('Failed to decode service response:', err, data);
	}
	return null;
}

function valueToText(value: unknown): string {
	if (value === null || value === undefined) return '';
	if (typeof value === 'string') return value;
	return JSON.stringify(value);
}

function textToValue(raw: string, defaultValue: unknown): unknown {
	const text = raw.trim();
	if (text === '') return null;
	if (typeof defaultValue === 'string' && !/^[[{]/.test(text)) return text;
	try {
		return JSON.parse(text);
	} catch {
		return text;
	}
}

function getErrorMessage(response: unknown, fallback: string) {
	const data = decodeServiceResponse(response);
	const error = data?.error;
	if (typeof error === 'string') return error;
	if (isRecord(error) && typeof error.message === 'string')
		return error.message;
	if (typeof data?.message === 'string') return data.message;
	return fallback;
}

export function MessageInput() {
	const { notify } = useNotifications();
	const connection = useDaiConnection();
	const [credentials, setCredentials] = useState({
		api_key: '',
		workspace_name: '',
		workflow_id: '',
	});
	const [workflowInterface, setWorkflowInterface] =
		useState<WorkflowInterface | null>(null);
	const [interfaceError, setInterfaceError] = useState(false);
	const [paramValues, setParamValues] = useState<Record<string, string>>({});
	const [submitting, setSubmitting] = useState(false);
	const [refreshing, setRefreshing] = useState(false);
	const [pipelineStatus, setPipelineStatus] = useState<PipelineStatus | null>(
		null,
	);
	const lastErrorToastRef = useRef<string | null>(null);

	const applyInterface = useCallback((data: unknown) => {
		const iface = decodeServiceResponse(data) as
			| (Partial<WorkflowInterface> & { status?: string })
			| null;
		if (!iface || iface.status !== 'ok' || !Array.isArray(iface.parameters)) {
			return false;
		}

		setWorkflowInterface(iface as WorkflowInterface);
		setInterfaceError(false);
		setPipelineStatus(iface.pipeline ?? null);

		const values: Record<string, string> = {};
		for (const param of iface.parameters) {
			values[param.name] = valueToText(param.current_value);
		}
		setParamValues(values);
		return true;
	}, []);

	const fetchInterface = useCallback(() => {
		setInterfaceError(false);
		postToRoboflowService(
			connection.daiConnection,
			INTERFACE_SERVICE,
			{},
			(data) => {
				if (!applyInterface(data)) {
					console.warn('Unexpected workflow interface response:', data);
					setInterfaceError(true);
				}
			},
			10_000,
			() => setInterfaceError(true),
		);
	}, [connection.daiConnection, applyInterface]);

	useEffect(() => {
		if (!connection.connected) return;
		fetchInterface();
	}, [connection.connected, fetchInterface]);

	useEffect(() => {
		if (!connection.connected) return;
		const id = window.setInterval(() => {
			if (submitting || refreshing) return;
			postToRoboflowService(
				connection.daiConnection,
				INTERFACE_SERVICE,
				{ quiet: true },
				(data) => {
					const iface = decodeServiceResponse(data) as
						| (Partial<WorkflowInterface> & { status?: string })
						| null;
					if (iface?.status === 'ok' && iface.pipeline) {
						setPipelineStatus(iface.pipeline);
					}
				},
				HEALTH_POLL_MS,
			);
		}, HEALTH_POLL_MS);
		return () => window.clearInterval(id);
	}, [connection.connected, connection.daiConnection, submitting, refreshing]);

	useEffect(() => {
		const message = pipelineStatus?.error?.message;
		if (message) {
			if (lastErrorToastRef.current !== message) {
				lastErrorToastRef.current = message;
				notify(`Roboflow pipeline error: ${message}`, {
					type: 'error',
					durationMs: 12000,
				});
			}
		} else {
			lastErrorToastRef.current = null;
		}
	}, [pipelineStatus, notify]);

	const handleRefresh = () => {
		if (!connection.connected) {
			notify('Not connected to device. Unable to refresh.', { type: 'error' });
			return;
		}

		setRefreshing(true);
		postToRoboflowService(
			connection.daiConnection,
			REFRESH_SERVICE,
			{},
			(data) => {
				setRefreshing(false);
				if (applyInterface(data)) {
					notify('Workflow definition refreshed', {
						type: 'success',
						durationMs: 3000,
					});
				} else {
					notify('Failed to refresh the workflow definition', {
						type: 'error',
					});
					fetchInterface();
				}
			},
			120_000,
			(response) => {
				setRefreshing(false);
				notify(
					getErrorMessage(
						response,
						'Failed to refresh the workflow definition',
					),
					{
						type: 'error',
					},
				);
			},
		);
	};

	const handleCredentialChange = (e: ChangeEvent<HTMLInputElement>) => {
		const { name, value } = e.target;
		setCredentials((prev) => ({ ...prev, [name]: value }));
	};

	const handleParamChange = (name: string, value: string) => {
		setParamValues((prev) => ({ ...prev, [name]: value }));
	};

	const buildPayload = (): Payload => {
		const workflowChanged = credentials.workflow_id.trim() !== '';

		let params: Record<string, unknown> | null = null;
		if (!workflowChanged && workflowInterface) {
			params = {};
			for (const param of workflowInterface.parameters) {
				const value = textToValue(
					paramValues[param.name] ?? '',
					param.default_value,
				);
				if (value !== null) params[param.name] = value;
			}
		}

		return {
			api_key: credentials.api_key.trim() || null,
			workspace_name: credentials.workspace_name.trim() || null,
			workflow_id: credentials.workflow_id.trim() || null,
			workflow_parameters: params,
		};
	};

	const handleSubmit = (e: FormEvent) => {
		e.preventDefault();

		if (!connection.connected) {
			notify('Not connected to device. Unable to submit parameters.', {
				type: 'error',
			});
			return;
		}

		const payload = buildPayload();
		console.log('Sending new Roboflow params to backend:', payload);
		setSubmitting(true);

		postToRoboflowService(
			connection.daiConnection,
			UPDATE_SERVICE,
			payload,
			(data) => {
				setSubmitting(false);
				if (!applyInterface(data)) {
					fetchInterface();
				}
				notify('Roboflow params updated', {
					type: 'success',
					durationMs: 3000,
				});
				setCredentials({ api_key: '', workspace_name: '', workflow_id: '' });
			},
			120_000,
			(response) => {
				setSubmitting(false);
				notify(getErrorMessage(response, 'Failed to update Roboflow params'), {
					type: 'error',
					durationMs: 8000,
				});
			},
		);
	};

	return (
		<section className="flex w-full max-w-full flex-col gap-4 text-left">
			<header className="flex flex-col gap-2">
				<h2 className="font-semibold">Adjust Roboflow Inference Parameters</h2>
				<div className="flex min-w-0 items-start justify-between gap-3">
					{workflowInterface ? (
						<p className="min-w-0 text-sm text-muted-foreground">
							Active workflow: <b>{workflowInterface.workflow_id}</b> (workspace{' '}
							<b>{workflowInterface.workspace_name}</b>)
						</p>
					) : interfaceError ? (
						<p className="text-sm text-destructive">
							Could not load the workflow interface.
						</p>
					) : (
						<p className="text-sm text-muted-foreground">
							Loading workflow interface...
						</p>
					)}
					<Button
						type="button"
						variant="ghost"
						size="sm"
						className="shrink-0"
						onClick={workflowInterface ? handleRefresh : fetchInterface}
						disabled={refreshing || submitting}
						title={
							workflowInterface
								? 'Re-fetch the workflow definition from Roboflow and restart inference'
								: 'Retry loading the workflow interface'
						}
						aria-label={
							workflowInterface
								? 'Refresh workflow definition'
								: 'Retry loading the workflow interface'
						}
					>
						{refreshing ? 'Refreshing...' : 'Refresh'}
					</Button>
				</div>
			</header>

			{pipelineStatus?.error ? (
				<div
					role="alert"
					className="break-words rounded-md border border-destructive bg-background p-3 text-sm text-destructive"
				>
					<b>
						Inference pipeline{' '}
						{pipelineStatus.running ? 'is failing' : 'stopped'}
						{pipelineStatus.error.error_type
							? ` (${pipelineStatus.error.error_type})`
							: ''}
						.
					</b>{' '}
					{pipelineStatus.error.message ?? 'No error details available.'}
					<p className="mt-1">
						Fix the workflow in the Roboflow builder and press Refresh, or
						submit different parameter values.
					</p>
				</div>
			) : pipelineStatus && !pipelineStatus.running ? (
				<p className="text-sm text-muted-foreground">
					Inference pipeline is starting...
				</p>
			) : null}

			<form onSubmit={handleSubmit} className="flex min-w-0 flex-col gap-4">
				<details>
					<summary className="mb-2 cursor-pointer font-medium">
						Workflow selection
					</summary>
					<div className="flex min-w-0 flex-col gap-3 pl-2">
						<label className="flex min-w-0 flex-col gap-1" htmlFor="api_key">
							<span className="font-medium">API Key</span>
							<Input
								id="api_key"
								type="text"
								name="api_key"
								value={credentials.api_key}
								onChange={handleCredentialChange}
								placeholder="Unchanged"
								className={inputClassName}
							/>
						</label>

						<label
							className="flex min-w-0 flex-col gap-1"
							htmlFor="workspace_name"
						>
							<span className="font-medium">Workspace Name</span>
							<Input
								id="workspace_name"
								type="text"
								name="workspace_name"
								value={credentials.workspace_name}
								onChange={handleCredentialChange}
								placeholder="Unchanged"
								className={inputClassName}
							/>
						</label>

						<label
							className="flex min-w-0 flex-col gap-1"
							htmlFor="workflow_id"
						>
							<span className="font-medium">Workflow ID</span>
							<Input
								id="workflow_id"
								type="text"
								name="workflow_id"
								value={credentials.workflow_id}
								onChange={handleCredentialChange}
								placeholder="Unchanged"
								className={inputClassName}
							/>
						</label>
					</div>
				</details>

				<details open>
					<summary className="mb-2 cursor-pointer font-medium">
						Workflow parameters
					</summary>
					<div className="flex min-w-0 flex-col gap-3 pl-2">
						{workflowInterface === null ? (
							<p className="text-muted-foreground">
								{interfaceError
									? 'Workflow parameters unavailable.'
									: 'Loading workflow interface...'}
							</p>
						) : workflowInterface.parameters.length === 0 ? (
							<p className="text-muted-foreground">
								This workflow does not expose any parameters. Add a{' '}
								<i>Workflow Parameter</i> input in the Roboflow workflow builder
								and it will show up here.
							</p>
						) : (
							workflowInterface.parameters.map((param) => (
								<label
									key={param.name}
									className="flex min-w-0 flex-col gap-1"
									htmlFor={`workflow-param-${param.name}`}
								>
									<span className="font-medium">
										{param.name}
										{param.kind?.length ? (
											<span className="ml-1 text-sm font-normal text-muted-foreground">
												({param.kind.join(', ')})
											</span>
										) : null}
									</span>
									<Input
										id={`workflow-param-${param.name}`}
										type={
											typeof param.default_value === 'number'
												? 'number'
												: 'text'
										}
										step="any"
										value={paramValues[param.name] ?? ''}
										onChange={(e) =>
											handleParamChange(param.name, e.target.value)
										}
										placeholder={
											param.default_value === null ||
											param.default_value === undefined
												? 'No default'
												: `Default: ${valueToText(param.default_value)}`
										}
										className={inputClassName}
									/>
								</label>
							))
						)}
					</div>
				</details>

				<Button
					type="submit"
					disabled={submitting || refreshing}
					className="mt-2 w-full justify-center"
				>
					{submitting ? 'Applying...' : 'Submit'}
				</Button>
			</form>
		</section>
	);
}
