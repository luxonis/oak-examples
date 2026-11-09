import { useDaiConnection } from '@luxonis/depthai-viewer-common';
import { Alert, Button, Flex, Label, SubLabel } from '@luxonis/ui-components';
import { useRef, useState } from 'react';
import { useNotifications } from './Notifications.tsx';
import { postToCustomService } from './services.ts';

type Props = {
	onDrawBBox?: () => void;
	getNextLabel?: () => string | null;
	onImagePromptAdded?: (label: string) => void;
	maxReached?: boolean;
};

export function ImageUploader({
	onDrawBBox,
	getNextLabel,
	onImagePromptAdded,
	maxReached,
}: Props) {
	const connection = useDaiConnection();
	const [selectedFile, setSelectedFile] = useState<File | null>(null);
	const fileInputRef = useRef<HTMLInputElement>(null);
	const { notify } = useNotifications();

	const handleFileSelect = (event: React.ChangeEvent<HTMLInputElement>) => {
		const file: File | null = event.target.files?.[0] || null;
		setSelectedFile(file);
		if (file) {
			notify(`Selected: ${file.name}`, { type: 'info', durationMs: 2000 });
		}
	};

	const handleUpload = () => {
		if (maxReached) {
			notify('Maximum image prompts reached. Delete some before adding more.', {
				type: 'warning',
				durationMs: 6000,
			});
			return;
		}
		if (!selectedFile) {
			notify('Please choose an image first', { type: 'warning' });
			return;
		}
		if (!connection.connected) {
			notify('Not connected to device. Unable to upload image.', {
				type: 'error',
			});
			return;
		}

		const dotIndex = selectedFile.name.lastIndexOf('.');
		const baseName = (
			dotIndex > 0 ? selectedFile.name.slice(0, dotIndex) : selectedFile.name
		).trim();
		const fallback = getNextLabel?.();
		const label = (baseName || fallback || '').trim();
		if (!label) {
			return;
		}

		const reader = new FileReader();
		reader.onload = () => {
			const fileData = reader.result;

			console.log('Uploading image to backend:', selectedFile.name);
			const sizeKb = Math.max(1, Math.round((selectedFile.size || 0) / 1024));
			notify(`Uploading ${selectedFile.name} (${sizeKb} KB)...`, {
				type: 'info',
			});

			postToCustomService(
				connection.daiConnection,
				'Image Upload Service',
				{
					filename: selectedFile.name,
					type: selectedFile.type,
					data: fileData,
					label,
				},
				(resp) => {
					console.log('[ImageUpload] Service ack:', resp);
					notify(`Image uploaded: ${selectedFile.name}`, {
						type: 'success',
						durationMs: 6000,
					});
					onImagePromptAdded?.(label);
				},
			);
		};

		reader.readAsDataURL(selectedFile);
	};

	return (
		<Flex direction="column" gap="sm">
			{maxReached && (
				<Alert
					intent="warning"
					variant="light"
					description="Image prompt limit reached. Delete or reset image prompts to add more."
				/>
			)}

			<Flex direction="column" gap="xs">
				<Label text="Upload an image of the object" />
				<input
					ref={fileInputRef}
					type="file"
					accept="image/*"
					className="hidden"
					onChange={handleFileSelect}
					disabled={maxReached}
				/>
				<div className="grid grid-cols-2 gap-2">
					<Button
						variant="outline"
						intent="gray"
						onClick={() => fileInputRef.current?.click()}
						disabled={maxReached}
					>
						Choose image
					</Button>
					<Button onClick={handleUpload} disabled={maxReached}>
						Upload image
					</Button>
				</div>
				<SubLabel
					break="word"
					text={selectedFile ? selectedFile.name : 'No image chosen.'}
				/>
			</Flex>

			<Flex direction="column" gap="xs">
				<Label text="Or draw a box around it on the stream" />
				<SubLabel text="Reset the view before drawing a bounding box." />
				<Button
					onClick={() => {
						console.log('[BBox] Button clicked: enabling drawing overlay');
						onDrawBBox?.();
						notify('Drawing mode enabled. Drag on the stream to draw a box.', {
							type: 'info',
							durationMs: 6000,
						});
					}}
					disabled={maxReached}
				>
					Draw bounding box
				</Button>
			</Flex>
		</Flex>
	);
}
