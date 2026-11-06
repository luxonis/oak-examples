import { useDaiConnection } from '@luxonis/depthai-viewer-common';
import { Badge, Button, Flex, Input, Label } from '@luxonis/ui-components';
import { type FormEvent, useRef, useState } from 'react';
import { postToObjectVolumeService } from './services.ts';

export function ClassSelector() {
	const inputRef = useRef<HTMLInputElement>(null);
	const connection = useDaiConnection();
	const [selectedClasses, setSelectedClasses] = useState<string[]>([
		'person',
		'chair',
		'TV',
	]);

	const handleSendMessage = (event: FormEvent) => {
		event.preventDefault();
		if (!inputRef.current) return;

		const updatedClasses = inputRef.current.value
			.split(',')
			.map((className) => className.trim())
			.filter(Boolean);

		if (updatedClasses.length === 0) return;

		console.log('Sending new class list to backend:', updatedClasses);

		postToObjectVolumeService(
			connection.daiConnection,
			'Class Update Service',
			updatedClasses,
			() => {
				console.log('Backend acknowledged class update');
				setSelectedClasses(updatedClasses);
			},
		);

		inputRef.current.value = '';
	};

	return (
		<Flex direction="column" gap="sm">
			<Flex direction="column" gap="xs">
				<Label id="ovm-active-classes-label" text="Active classes" />
				<ul
					aria-labelledby="ovm-active-classes-label"
					className="flex flex-wrap gap-2"
				>
					{selectedClasses.map((className) => (
						<li key={className}>
							<Badge intent="gray" variant="light" label={className} />
						</li>
					))}
				</ul>
			</Flex>

			<form onSubmit={handleSendMessage}>
				<Flex direction="column" gap="xs">
					<label htmlFor="ovm-class-input">
						<Label text="New classes, separated by commas" />
					</label>
					<div className="grid grid-cols-[minmax(0,1fr)_auto] items-center gap-2">
						<Input
							id="ovm-class-input"
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
