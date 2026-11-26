import { useDaiConnection } from '@luxonis/depthai-viewer-common';
import {
	Badge,
	Button,
	Flex,
	Input,
	Label,
	SubLabel,
} from '@luxonis/ui-components';
import { type FormEvent, useRef, useState } from 'react';
import { useNotifications } from './Notifications.tsx';
import { postToCustomService } from './services.ts';

interface ClassSelectorProps {
	initialClasses?: string[];
	onClassesUpdated?: (classes: string[]) => void;
}

export function ClassSelector({
	initialClasses = [],
	onClassesUpdated,
}: ClassSelectorProps) {
	const inputRef = useRef<HTMLInputElement>(null);
	const connection = useDaiConnection();
	const [selectedClasses, setSelectedClasses] =
		useState<string[]>(initialClasses);
	const { notify } = useNotifications();

	const handleSendMessage = (event: FormEvent) => {
		event.preventDefault();
		if (inputRef.current) {
			const value = inputRef.current.value;
			const updatedClasses = value
				.split(',')
				.map((c: string) => c.trim())
				.filter(Boolean);

			if (updatedClasses.length === 0) {
				notify('Please enter at least one class (comma separated).', {
					type: 'warning',
					durationMs: 5000,
				});
				return;
			}
			if (!connection.connected) {
				notify('Not connected to device. Unable to update classes.', {
					type: 'error',
				});
				return;
			}

			console.log('Sending new class list to backend:', updatedClasses);
			notify(
				`Updating ${updatedClasses.length} class${updatedClasses.length > 1 ? 'es' : ''}...`,
				{ type: 'info' },
			);

			postToCustomService(
				connection.daiConnection,
				'Class Update Service',
				updatedClasses,
				() => {
					console.log('Backend acknowledged class update');
					setSelectedClasses(updatedClasses);
					notify(`Classes updated (${updatedClasses.join(', ')})`, {
						type: 'success',
						durationMs: 6000,
					});
					onClassesUpdated?.(updatedClasses);
				},
			);

			inputRef.current.value = '';
		}
	};

	return (
		<Flex direction="column" gap="sm">
			<Flex direction="column" gap="xs">
				<Label id="active-classes-label" text="Active classes" />
				{selectedClasses.length > 0 ? (
					<ul
						aria-labelledby="active-classes-label"
						className="flex flex-wrap gap-2"
					>
						{selectedClasses.map((cls) => (
							<li key={cls}>
								<Badge intent="gray" variant="light" label={cls} />
							</li>
						))}
					</ul>
				) : (
					<SubLabel text="No classes selected." />
				)}
			</Flex>

			<form onSubmit={handleSendMessage}>
				<Flex direction="column" gap="xs">
					<label htmlFor="class-input">
						<Label text="New classes, separated by commas" />
					</label>
					<div className="grid grid-cols-[minmax(0,1fr)_auto] items-center gap-2">
						<Input
							id="class-input"
							type="text"
							placeholder="person, chair, TV"
							ref={inputRef}
						/>
						<Button type="submit">Update classes</Button>
					</div>
				</Flex>
			</form>
		</Flex>
	);
}
