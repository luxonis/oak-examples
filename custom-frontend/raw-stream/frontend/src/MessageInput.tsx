import { useDaiConnection } from '@luxonis/depthai-viewer-common';
import { Button, Flex, Input } from '@luxonis/ui-components';
import { useRef } from 'react';

export function MessageInput() {
	const connection = useDaiConnection();
	const inputRef = useRef<HTMLInputElement>(null);

	const handleSendMessage = () => {
		if (inputRef.current) {
			const message = inputRef.current.value;
			const messageService = 'Message Service' as Parameters<
				NonNullable<typeof connection.daiConnection>['postToService']
			>[0];

			console.log('Sending message:', message);
			connection.daiConnection?.postToService(
				messageService,
				message,
				(response) => {
					console.log('Received response:', response);
				},
			);

			inputRef.current.value = '';
		}
	};

	return (
		<Flex direction="row" gap="sm" align="center">
			<Input type="text" placeholder="Message" ref={inputRef} />

			<Button onClick={handleSendMessage}>Send</Button>
		</Flex>
	);
}
