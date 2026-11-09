import { useDaiConnection } from '@luxonis/depthai-viewer-common';
import {
	Button,
	Flex,
	Separator,
	SubLabel,
	useToast,
} from '@luxonis/ui-components';
import { type ChangeEvent, useRef, useState } from 'react';
import { postToDataCollectionService } from '../../services.ts';

type Props = {
	onDrawBBox?: () => void;
	onResetView?: () => void;
	resetViewDisabled?: boolean;
	drawBBoxDisabled?: boolean;
};

export function ImageUploader({
	onDrawBBox,
	onResetView,
	resetViewDisabled,
	drawBBoxDisabled,
}: Props) {
	const connection = useDaiConnection();
	const [selectedFile, setSelectedFile] = useState<File | null>(null);
	const fileInputRef = useRef<HTMLInputElement>(null);
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
		<Flex direction="column" gap="sm">
			<SubLabel text="Upload an image or draw a box to switch to image mode." />

			<Flex direction="column" gap="xs">
				<input
					ref={fileInputRef}
					type="file"
					accept="image/*"
					onChange={handleFileSelect}
					className="hidden"
				/>
				<div className="grid grid-cols-2 gap-2">
					<Button
						variant="outline"
						intent="gray"
						onClick={() => fileInputRef.current?.click()}
					>
						Choose image
					</Button>
					<Button onClick={handleUpload}>Upload image</Button>
				</div>
				<SubLabel
					aria-live="polite"
					text={selectedFile ? selectedFile.name : 'No image selected'}
				/>
			</Flex>

			<Separator />

			<Flex direction="column" gap="xs">
				<SubLabel text="Reset the view before drawing if the stream is zoomed or panned." />
				<div className="grid grid-cols-2 gap-2">
					<Button
						variant="outline"
						intent="gray"
						onClick={onResetView}
						disabled={resetViewDisabled}
					>
						Reset view
					</Button>
					<Button
						variant="outline"
						intent="gray"
						disabled={drawBBoxDisabled}
						onClick={() => {
							console.log('[BBox] Button clicked: enabling drawing overlay');
							onDrawBBox?.();
							toast({
								description:
									'Drawing mode enabled. Reset the view first if the stream is zoomed or panned.',
								colorVariant: 'gray',
								duration: 'long',
							});
						}}
					>
						Draw bounding box
					</Button>
				</div>
			</Flex>
		</Flex>
	);
}
