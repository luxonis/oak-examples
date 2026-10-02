import { useDaiConnection } from '@luxonis/depthai-viewer-common';
import { Button, Input } from '@luxonis/ui-components';
import { useRef, useState } from 'react';
import { postToObjectVolumeService } from './services.ts';

export function ClassSelector() {
	const inputRef = useRef<HTMLInputElement>(null);
	const connection = useDaiConnection();
	const [selectedClasses, setSelectedClasses] = useState<string[]>([
		'person',
		'chair',
		'TV',
	]);

	const handleSendMessage = () => {
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
		<div className="flex flex-col gap-4">
			<h3 className="font-semibold">Update Classes with Text Input:</h3>
			<div className="rounded-md border border-border bg-card p-4 text-sm">
				<ul className="m-0 list-disc pl-6">
					{selectedClasses.map((className) => (
						<li key={className}>{className}</li>
					))}
				</ul>
			</div>

			<div className="grid min-w-0 grid-cols-[minmax(0,1fr)_auto] items-center gap-3 p-1">
				<Input
					className="min-w-0 w-full"
					type="text"
					placeholder="person,chair,TV"
					ref={inputRef}
				/>
				<Button
					className="shrink-0 whitespace-nowrap px-4"
					onClick={handleSendMessage}
				>
					Update Classes
				</Button>
			</div>
		</div>
	);
}
