import { useDaiConnection } from '@luxonis/depthai-viewer-common';
import { Button, Input, Switch } from '@luxonis/ui-components';
import { useEffect, useMemo, useState } from 'react';
import { useNotifications } from './Notifications.tsx';
import { postToQRTilingService } from './services.ts';

export type TilingParams = {
	rows: number;
	cols: number;
	overlap: number;
	global_detection: boolean;
	grid_matrix: number[][] | null;
};

interface TilingControlProps {
	initialParams: TilingParams;
}

function getCellColor(index: number): string {
	const hue = (index * 137.508) % 360;
	return `hsl(${hue}, 70%, 60%)`;
}

function createDefaultMatrix(rows: number, cols: number): number[][] {
	const matrix: number[][] = [];
	let index = 0;
	for (let r = 0; r < rows; r++) {
		const row: number[] = [];
		for (let c = 0; c < cols; c++) {
			row.push(index++);
		}
		matrix.push(row);
	}
	return matrix;
}

function matricesEqual(a: number[][], b: number[][]): boolean {
	if (a.length !== b.length) return false;
	for (let r = 0; r < a.length; r++) {
		if (a[r].length !== b[r].length) return false;
		for (let c = 0; c < a[r].length; c++) {
			if (a[r][c] !== b[r][c]) return false;
		}
	}
	return true;
}

function isAdjacentToValue(
	matrix: number[][],
	row: number,
	col: number,
	value: number,
): boolean {
	const neighbors = [
		[row - 1, col],
		[row + 1, col],
		[row, col - 1],
		[row, col + 1],
	];

	for (const [r, c] of neighbors) {
		if (r >= 0 && r < matrix.length && c >= 0 && c < matrix[0].length) {
			if (matrix[r][c] === value) return true;
		}
	}
	return false;
}

interface GridMatrixEditorProps {
	rows: number;
	cols: number;
	matrix: number[][];
	selectedValue: number | null;
	onCellClick: (row: number, col: number) => void;
}

function GridMatrixEditor({
	rows,
	cols,
	matrix,
	selectedValue,
	onCellClick,
}: GridMatrixEditorProps) {
	const valueCounts = new Map<number, number>();
	for (let r = 0; r < rows; r++) {
		for (let c = 0; c < cols; c++) {
			const val = matrix[r]?.[c] ?? 0;
			valueCounts.set(val, (valueCounts.get(val) ?? 0) + 1);
		}
	}

	return (
		<div
			className="grid gap-0.5"
			style={{ gridTemplateColumns: `repeat(${cols}, 2.25rem)` }}
		>
			{Array.from({ length: rows }).map((_, rowIdx) =>
				Array.from({ length: cols }).map((_, colIdx) => {
					const cellValue = matrix[rowIdx]?.[colIdx] ?? 0;
					const isSelected = selectedValue === cellValue;
					const isMerged = (valueCounts.get(cellValue) ?? 0) > 1;
					const color = isMerged ? getCellColor(cellValue) : '#ffffff';
					const borderColor = isSelected
						? isMerged
							? color
							: '#2563eb'
						: 'rgba(15, 23, 42, 0.22)';

					return (
						<button
							// biome-ignore lint/suspicious/noArrayIndexKey: Tiles are addressed by fixed grid coordinates.
							key={`${rowIdx}-${colIdx}`}
							type="button"
							aria-label={`Tile ${rowIdx + 1}, ${colIdx + 1}`}
							className="h-9 w-9 cursor-pointer rounded border bg-white transition-shadow"
							onClick={() => onCellClick(rowIdx, colIdx)}
							style={{
								backgroundColor: color,
								borderColor,
								borderWidth: isSelected ? 3 : 1,
								boxShadow: isSelected ? `0 0 8px ${borderColor}` : 'none',
							}}
						/>
					);
				}),
			)}
		</div>
	);
}

function clamp(value: number, min: number, max: number) {
	return Math.max(min, Math.min(max, value));
}

export function TilingControl({ initialParams }: TilingControlProps) {
	const connection = useDaiConnection();
	const { notify } = useNotifications();

	const [rows, setRows] = useState(initialParams.rows);
	const [cols, setCols] = useState(initialParams.cols);
	const [rowsInput, setRowsInput] = useState(String(initialParams.rows));
	const [colsInput, setColsInput] = useState(String(initialParams.cols));
	const [overlap, setOverlap] = useState(initialParams.overlap);
	const [overlapInput, setOverlapInput] = useState(
		String(initialParams.overlap),
	);
	const [globalDetection, setGlobalDetection] = useState(
		initialParams.global_detection,
	);
	const [gridMatrix, setGridMatrix] = useState<number[][]>(
		initialParams.grid_matrix ??
			createDefaultMatrix(initialParams.rows, initialParams.cols),
	);
	const [selectedValue, setSelectedValue] = useState<number | null>(null);
	const [userChangedSize, setUserChangedSize] = useState(false);

	useEffect(() => {
		setRows(initialParams.rows);
		setCols(initialParams.cols);
		setRowsInput(String(initialParams.rows));
		setColsInput(String(initialParams.cols));
		setOverlap(initialParams.overlap);
		setOverlapInput(String(initialParams.overlap));
		setGlobalDetection(initialParams.global_detection);
		setGridMatrix(
			initialParams.grid_matrix ??
				createDefaultMatrix(initialParams.rows, initialParams.cols),
		);
		setSelectedValue(null);
		setUserChangedSize(false);
	}, [initialParams]);

	const defaultMatrix = useMemo(
		() => createDefaultMatrix(rows, cols),
		[rows, cols],
	);
	const isGridModified = !matricesEqual(gridMatrix, defaultMatrix);

	useEffect(() => {
		if (!userChangedSize) return;

		setGridMatrix(createDefaultMatrix(rows, cols));
		setSelectedValue(null);
		setUserChangedSize(false);
	}, [rows, cols, userChangedSize]);

	const handleRowsChange = (newRows: number) => {
		if (newRows !== rows) {
			setUserChangedSize(true);
			setRows(newRows);
		}
	};

	const handleColsChange = (newCols: number) => {
		if (newCols !== cols) {
			setUserChangedSize(true);
			setCols(newCols);
		}
	};

	const handleCellClick = (row: number, col: number) => {
		const clickedValue = gridMatrix[row][col];

		if (selectedValue === null) {
			setSelectedValue(clickedValue);
			return;
		}

		if (clickedValue === selectedValue) {
			setSelectedValue(null);
			return;
		}

		if (isAdjacentToValue(gridMatrix, row, col, selectedValue)) {
			setGridMatrix((current) =>
				current.map((gridRow, rIdx) =>
					gridRow.map((cell, cIdx) =>
						rIdx === row && cIdx === col ? selectedValue : cell,
					),
				),
			);
			return;
		}

		setSelectedValue(clickedValue);
	};

	const handleUpdate = () => {
		if (!connection.connected) {
			notify('Not connected to device. Unable to update tiling.', {
				type: 'error',
			});
			return;
		}

		const config = {
			rows,
			cols,
			overlap,
			global_detection: globalDetection,
			grid_matrix: gridMatrix,
		};

		postToQRTilingService(
			connection.daiConnection,
			'Tiling Config Service',
			config,
			() => {
				notify('Tiling configuration updated', {
					type: 'success',
					durationMs: 2500,
				});
			},
		);
	};

	return (
		<section className="flex flex-col gap-5 border-t border-border pt-4">
			<h2 className="font-semibold">Tiling Configuration</h2>

			<div className="grid grid-cols-2 gap-3">
				<div className="flex min-w-0 flex-col gap-2">
					<label htmlFor="qr-tiling-rows" className="text-sm font-medium">
						Rows
					</label>
					<Input
						id="qr-tiling-rows"
						className="w-full min-w-0"
						type="number"
						value={rowsInput}
						onChange={(e) => {
							const raw = e.target.value;
							setRowsInput(raw);
							if (raw === '') return;
							const num = Number.parseInt(raw, 10);
							if (!Number.isNaN(num)) {
								const clamped = clamp(num, 1, 8);
								setRowsInput(String(clamped));
								handleRowsChange(clamped);
							}
						}}
						onBlur={() => {
							if (rowsInput === '') setRowsInput(String(rows));
						}}
						onFocus={(e) => e.target.select()}
						min={1}
						max={8}
					/>
				</div>

				<div className="flex min-w-0 flex-col gap-2">
					<label htmlFor="qr-tiling-cols" className="text-sm font-medium">
						Columns
					</label>
					<Input
						id="qr-tiling-cols"
						className="w-full min-w-0"
						type="number"
						value={colsInput}
						onChange={(e) => {
							const raw = e.target.value;
							setColsInput(raw);
							if (raw === '') return;
							const num = Number.parseInt(raw, 10);
							if (!Number.isNaN(num)) {
								const clamped = clamp(num, 1, 8);
								setColsInput(String(clamped));
								handleColsChange(clamped);
							}
						}}
						onBlur={() => {
							if (colsInput === '') setColsInput(String(cols));
						}}
						onFocus={(e) => e.target.select()}
						min={1}
						max={8}
					/>
				</div>
			</div>

			<div className="flex min-w-0 flex-col gap-2">
				<label htmlFor="qr-tiling-overlap" className="text-sm font-medium">
					Overlap
				</label>
				<Input
					id="qr-tiling-overlap"
					className="w-full min-w-0"
					type="number"
					value={overlapInput}
					onChange={(e) => {
						const raw = e.target.value;
						setOverlapInput(raw);
						if (raw === '') return;
						const val = Number.parseFloat(raw);
						if (!Number.isNaN(val)) {
							const clamped = clamp(val, 0, 0.99);
							setOverlap(clamped);
						}
					}}
					onBlur={() => {
						setOverlapInput(String(overlap));
					}}
					min={0}
					max={0.99}
					step={0.05}
				/>
			</div>

			<div className="flex items-center justify-between gap-4">
				<span className="text-sm font-medium">
					Global Detection (include full image)
				</span>
				<Switch value={globalDetection} onChange={setGlobalDetection} />
			</div>

			<div className="flex flex-col gap-3">
				<GridMatrixEditor
					rows={rows}
					cols={cols}
					matrix={gridMatrix}
					selectedValue={selectedValue}
					onCellClick={handleCellClick}
				/>

				<Button
					variant="outline"
					onClick={() => {
						setGridMatrix(createDefaultMatrix(rows, cols));
						setSelectedValue(null);
					}}
					disabled={!isGridModified}
				>
					Reset Grid
				</Button>
			</div>

			<Button onClick={handleUpdate}>Update Tiling</Button>
		</section>
	);
}
