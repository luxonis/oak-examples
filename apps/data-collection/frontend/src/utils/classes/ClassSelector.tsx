import { useDaiConnection } from '@luxonis/depthai-viewer-common';
import { Button, Input, useToast } from '@luxonis/ui-components';
import { useEffect, useRef, useState } from 'react';
import { postToDataCollectionService } from '../../services.ts';

interface ClassSelectorProps {
	initialClasses?: string[];
}

export function ClassSelector({ initialClasses }: ClassSelectorProps) {
	const inputRef = useRef<HTMLInputElement>(null);
	const connection = useDaiConnection();
	const [selectedClasses, setSelectedClasses] = useState<string[]>([
		'person',
		'chair',
		'TV',
	]);
	const { toast } = useToast();

	useEffect(() => {
		if (initialClasses && initialClasses.length > 0) {
			console.log(
				'[ClassSelector] Restoring classes from backend:',
				initialClasses,
			);
			setSelectedClasses([...initialClasses]);
		}
	}, [initialClasses]);

	const handleSendMessage = () => {
		const value = inputRef.current?.value ?? '';
		const updatedClasses = value
			.split(',')
			.map((className) => className.trim())
			.filter(Boolean);

		if (updatedClasses.length === 0) {
			toast({
				description: 'Please enter at least one class (comma separated).',
				colorVariant: 'warning',
				duration: 'long',
			});
			return;
		}

		if (!connection.connected) {
			toast({
				description: 'Not connected to device. Unable to update classes.',
				colorVariant: 'error',
			});
			return;
		}

		console.log('Sending new class list to backend:', updatedClasses);
		toast({
			description: `Updating ${updatedClasses.length} class${
				updatedClasses.length > 1 ? 'es' : ''
			}...`,
			colorVariant: 'gray',
		});

		postToDataCollectionService(
			connection.daiConnection,
			'Class Update Service',
			{ classes: updatedClasses },
			() => {
				console.log('Backend acknowledged class update');
				setSelectedClasses(updatedClasses);
				toast({
					description: `Classes updated (${updatedClasses.join(', ')})`,
					colorVariant: 'success',
					duration: 'long',
				});
			},
		);

		if (inputRef.current) {
			inputRef.current.value = '';
		}
	};

	return (
		<div className="flex flex-col gap-4">
			<h3 className="font-semibold">Update Classes with Text Input:</h3>
			<ul className="list-disc pl-6">
				{selectedClasses.map((className) => (
					<li key={className}>{className}</li>
				))}
			</ul>

			<div className="flex min-w-0 flex-row items-center gap-3 p-1">
				<Input
					className="min-w-0 flex-1"
					type="text"
					placeholder="person,chair,TV"
					ref={inputRef}
				/>
				<Button className="shrink-0" onClick={handleSendMessage}>
					Update Classes
				</Button>
			</div>
		</div>
	);
}
