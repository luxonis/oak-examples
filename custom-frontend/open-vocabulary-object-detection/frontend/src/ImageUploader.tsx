import { useDaiConnection } from '@luxonis/depthai-viewer-common';
import { Button, Flex } from '@luxonis/ui-components';
import { useState } from 'react';
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
		<div className="flex flex-col gap-4">
			<h3 className="font-semibold">Update Classes with Image Input:</h3>
			<span className="text-sm text-muted-foreground">
				Reset the view before drawing a bounding box.
			</span>
			{maxReached && (
				<span className="text-sm text-destructive">
					Maximum number of image prompts reached. Please delete or reset image
					prompts to add more.
				</span>
			)}

			<label
				htmlFor="fileInput"
				className={`rounded-md border-2 border-dashed border-muted-foreground/50 bg-muted p-8 text-center ${
					maxReached
						? 'cursor-not-allowed opacity-60'
						: 'cursor-pointer hover:bg-accent'
				}`}
			>
				{selectedFile
					? selectedFile.name
					: 'Click here to choose an image file.'}
			</label>

			<input
				id="fileInput"
				type="file"
				accept="image/*"
				onChange={handleFileSelect}
				style={{ display: 'none' }}
				disabled={maxReached}
			/>

			<Flex
				direction="row"
				align="center"
				justify="center"
				gap="md"
				className="mt-8"
			>
				<Button onClick={handleUpload} disabled={maxReached}>
					Upload Image
				</Button>

				<span>or</span>

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
					Draw Bounding Box
				</Button>
			</Flex>
		</div>
	);
}
