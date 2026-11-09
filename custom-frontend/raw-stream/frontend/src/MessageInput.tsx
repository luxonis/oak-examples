import { useDaiConnection } from '@luxonis/depthai-viewer-common';
import { Button, Card, Flex, Input, SubLabel } from '@luxonis/ui-components';
import { type FormEvent, useState } from 'react';

type Status =
	| { kind: 'idle' }
	| { kind: 'sending' }
	| { kind: 'answered'; text: string }
	| { kind: 'failed'; text: string };

export function MessageInput() {
	const connection = useDaiConnection();
	const [message, setMessage] = useState('');
	const [status, setStatus] = useState<Status>({ kind: 'idle' });

	const handleSubmit = (event: FormEvent) => {
		event.preventDefault();
		const messageService = 'Message Service' as Parameters<
			NonNullable<typeof connection.daiConnection>['postToService']
		>[0];

		const daiConnection = connection.daiConnection;
		if (!daiConnection) return;

		const fail = (text: string) => setStatus({ kind: 'failed', text });
		setStatus({ kind: 'sending' });
		daiConnection
			.postToService(
				messageService,
				message,
				(response) => {
					setStatus({ kind: 'answered', text: JSON.stringify(response) });
				},
				(response) => fail(String(response?.error ?? 'No response.')),
			)
			.catch((error: unknown) => fail(String(error)));
		setMessage('');
	};

	return (
		<Card title="Message Service" variant="outline" intent="white">
			<form onSubmit={handleSubmit}>
				<Flex direction="column" gap="sm">
					<label htmlFor="message">
						<SubLabel text="Message sent to the Python backend" />
					</label>
					<Flex direction="row" gap="sm" align="center">
						<Input
							id="message"
							value={message}
							placeholder="Message"
							onChange={(event) => setMessage(event.target.value)}
						/>
						<Button
							type="submit"
							disabled={!connection.connected || status.kind === 'sending'}
						>
							Send
						</Button>
					</Flex>
					{status.kind === 'answered' ? (
						<SubLabel text={`Response: ${status.text}`} />
					) : null}
					{status.kind === 'failed' ? (
						<SubLabel color="error" text={`Request failed: ${status.text}`} />
					) : null}
				</Flex>
			</form>
		</Card>
	);
}
