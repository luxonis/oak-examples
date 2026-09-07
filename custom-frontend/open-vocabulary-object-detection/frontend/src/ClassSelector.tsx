import { useDaiConnection } from '@luxonis/depthai-viewer-common';
import { Button, Input } from '@luxonis/ui-components';
import { useRef, useState } from 'react';
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

	const handleSendMessage = () => {
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
		<div className="flex flex-col gap-4">
			<h3 className="font-semibold">Update Classes with Text Input:</h3>

			<div className="max-h-[150px] overflow-y-auto rounded-md border border-border bg-card p-4 text-left">
				{selectedClasses.length > 0 ? (
					<ul className="m-0 list-disc pl-6">
						{selectedClasses.map((cls) => (
							<li key={cls}>{cls}</li>
						))}
					</ul>
				) : (
					<p className="text-sm text-muted-foreground">No classes selected.</p>
				)}
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
