import { useDaiConnection } from '@luxonis/depthai-viewer-common';
import {
	Badge,
	Button,
	Flex,
	Input,
	Label,
	SubLabel,
	useToast,
} from '@luxonis/ui-components';
import { useEffect, useId, useRef, useState } from 'react';
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
	const inputId = useId();
	const helpId = useId();

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
		<Flex direction="column" gap="sm">
			<Flex direction="column" gap="xs">
				<Label text="Current classes" />
				<ul className="flex flex-wrap gap-2" aria-label="Current classes">
					{selectedClasses.map((className) => (
						<li key={className}>
							<Badge intent="gray" variant="light" label={className} />
						</li>
					))}
				</ul>
			</Flex>

			<Flex direction="column" gap="xs">
				<label htmlFor={inputId}>
					<Label text="Labels to find" />
				</label>
				<Flex direction="row" align="center" gap="xs">
					<Input
						id={inputId}
						className="min-w-0 flex-1"
						type="text"
						placeholder="person,chair,TV"
						aria-describedby={helpId}
						ref={inputRef}
					/>
					<Button className="shrink-0" onClick={handleSendMessage}>
						Update classes
					</Button>
				</Flex>
				<SubLabel
					id={helpId}
					text="Comma separated, for example person, chair, TV."
				/>
			</Flex>
		</Flex>
	);
}
