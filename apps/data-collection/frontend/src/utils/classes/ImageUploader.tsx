import { useDaiConnection } from '@luxonis/depthai-viewer-common';
import { Button, useToast } from '@luxonis/ui-components';
import { type ChangeEvent, useState } from 'react';
import { postToDataCollectionService } from '../../services.ts';

type Props = {
	onDrawBBox?: () => void;
};

export function ImageUploader({ onDrawBBox }: Props) {
	const connection = useDaiConnection();
	const [selectedFile, setSelectedFile] = useState<File | null>(null);
	const { toast } = useToast();

	const handleFileSelect = (event: ChangeEvent<HTMLInputElement>) => {
		const file = event.target.files?.[0] || null;
		setSelectedFile(file);
		if (file) {
			toast({
				description: `Selected: ${file.name}`,
				colorVariant: 'gray',
			});
		}
	};

	const handleUpload = () => {
		if (!selectedFile) {
			toast({
				description: 'Please choose an image first',
				colorVariant: 'warning',
			});
			return;
		}

		if (!connection.connected) {
			toast({
				description: 'Not connected to device. Unable to upload image.',
				colorVariant: 'error',
			});
			return;
		}

		const reader = new FileReader();
		reader.onload = () => {
			const fileData = reader.result;

			if (typeof fileData !== 'string') {
				toast({
					description: 'Unable to read image file.',
					colorVariant: 'error',
				});
				return;
			}

			console.log('Uploading image to backend:', selectedFile.name);
			const sizeKb = Math.max(1, Math.round((selectedFile.size || 0) / 1024));
			toast({
				description: `Uploading ${selectedFile.name} (${sizeKb} KB)...`,
				colorVariant: 'gray',
			});

			postToDataCollectionService(
				connection.daiConnection,
				'Image Upload Service',
				{
					filename: selectedFile.name,
					type: selectedFile.type,
					data: fileData,
				},
				(resp) => {
					console.log('[ImageUpload] Service ack:', resp);
					toast({
						description: `Image uploaded: ${selectedFile.name}`,
						colorVariant: 'success',
						duration: 'long',
					});
				},
			);
		};

		reader.readAsDataURL(selectedFile);
	};

	return (
		<div className="flex flex-col gap-4">
			<h3 className="font-semibold">Update Classes with Image Input:</h3>
			<span className="text-sm text-muted-foreground">
				Important: reset view before drawing a bounding box
			</span>

			<label
				htmlFor="fileInput"
				className="cursor-pointer rounded-md border-2 border-dashed border-border bg-muted p-4 text-center transition-colors hover:bg-muted/80"
			>
				{selectedFile
					? selectedFile.name
					: 'Click here to choose an image file'}
			</label>

			<input
				id="fileInput"
				type="file"
				accept="image/*"
				onChange={handleFileSelect}
				className="hidden"
			/>

			<div className="flex flex-row flex-wrap items-center gap-3">
				<Button onClick={handleUpload}>Upload Image</Button>
				<span className="text-muted-foreground">or</span>
				<Button
					variant="outline"
					onClick={() => {
						console.log('[BBox] Button clicked: enabling drawing overlay');
						onDrawBBox?.();
						toast({
							description:
								'Drawing mode enabled. Drag on the stream to draw a box.',
							colorVariant: 'gray',
							duration: 'long',
						});
					}}
				>
					Draw Bounding Box
				</Button>
			</div>
		</div>
	);
}
