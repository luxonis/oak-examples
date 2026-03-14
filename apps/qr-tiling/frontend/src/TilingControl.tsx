import { Flex, Button, Input, Checkbox } from "@luxonis/common-fe-components";
import { useState, useEffect, useMemo } from "react";
import { useDaiConnection } from "@luxonis/depthai-viewer-common";

export type TilingParams = {
    rows: number;
    cols: number;
    overlap: number;
    global_detection: boolean;
    grid_matrix: number[][];
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
    value: number
): boolean {
    const neighbors = [
        [row - 1, col],
        [row + 1, col],
        [row, col - 1],
        [row, col + 1],
    ];

    for (const [r, c] of neighbors) {
        if (r >= 0 && r < matrix.length && c >= 0 && c < matrix[0].length) {
            if (matrix[r][c] === value) {
                return true;
            }
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
        <div style={{ display: "flex", flexDirection: "column", gap: 2 }}>
            {Array.from({ length: rows }).map((_, rowIdx) => (
                <div key={rowIdx} style={{ display: "flex", gap: 2 }}>
                    {Array.from({ length: cols }).map((_, colIdx) => {
                        const cellValue = matrix[rowIdx]?.[colIdx] ?? 0;
                        const isSelected = selectedValue === cellValue;
                        const isMerged = (valueCounts.get(cellValue) ?? 0) > 1;

                        const color = isMerged
                            ? getCellColor(cellValue)
                            : "#ffffff";
                        const borderColor = isSelected
                            ? isMerged
                                ? color
                                : "#2196F3"
                            : "rgba(0,0,0,0.2)";

                        return (
                            <div
                                key={colIdx}
                                onClick={() => onCellClick(rowIdx, colIdx)}
                                style={{
                                    width: 40,
                                    height: 40,
                                    backgroundColor: color,
                                    cursor: "pointer",
                                    borderRadius: 4,
                                    border: isSelected
                                        ? `3px solid ${borderColor}`
                                        : `1px solid ${borderColor}`,
                                    boxShadow: isSelected
                                        ? `0 0 8px ${borderColor}`
                                        : "none",
                                }}
                            />
                        );
                    })}
                </div>
            ))}
        </div>
    );
}

export function TilingControl({ initialParams }: TilingControlProps) {
    const connection = useDaiConnection();

    const [rows, setRows] = useState(initialParams.rows);
    const [cols, setCols] = useState(initialParams.cols);
    const [rowsInput, setRowsInput] = useState(String(initialParams.rows));
    const [colsInput, setColsInput] = useState(String(initialParams.cols));
    const [overlap, setOverlap] = useState(initialParams.overlap);
    const [globalDetection, setGlobalDetection] = useState(initialParams.global_detection);
    const [gridMatrix, setGridMatrix] = useState<number[][]>(
        initialParams.grid_matrix ?? createDefaultMatrix(initialParams.rows, initialParams.cols)
    );
    const [selectedValue, setSelectedValue] = useState<number | null>(null);
    const [userChangedSize, setUserChangedSize] = useState(false);

    const defaultMatrix = useMemo(() => createDefaultMatrix(rows, cols), [rows, cols]);
    const isGridModified = !matricesEqual(gridMatrix, defaultMatrix);

    useEffect(() => {
        if (userChangedSize) {
            setGridMatrix(createDefaultMatrix(rows, cols));
            setSelectedValue(null);
            setUserChangedSize(false);
        }
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

        const isAdjacent = isAdjacentToValue(gridMatrix, row, col, selectedValue);

        if (isAdjacent) {
            const newMatrix = gridMatrix.map((r, rIdx) =>
                r.map((c, cIdx) =>
                    rIdx === row && cIdx === col ? selectedValue : c
                )
            );
            setGridMatrix(newMatrix);
        } else {
            setSelectedValue(clickedValue);
        }
    };

    const handleUpdate = () => {
        const config = {
            rows,
            cols,
            overlap,
            global_detection: globalDetection,
            grid_matrix: gridMatrix,
        };

        (connection as any).daiConnection?.postToService(
            "Tiling Config Service",
            config
        );
    };

    return (
        <Flex direction="column" gap="md">
            <span style={{ fontSize: 16, fontWeight: "bold" }}>
                Tiling Configuration
            </span>

            <Flex direction="row" gap="sm" alignItems="center">
                <span>Rows:</span>
                <Input
                    type="number"
                    value={rowsInput}
                    onChange={(e) => {
                        const raw = e.target.value;
                        if (raw === "") { setRowsInput(raw); return; }
                        const num = parseInt(raw);
                        if (!isNaN(num)) {
                            const clamped = Math.max(1, Math.min(8, num));
                            setRowsInput(String(clamped));
                            handleRowsChange(clamped);
                        }
                    }}
                    onFocus={(e) => e.target.select()}
                    min={1}
                    max={8}
                    style={{ width: 60 }}
                />

                <span>Cols:</span>
                <Input
                    type="number"
                    value={colsInput}
                    onChange={(e) => {
                        const raw = e.target.value;
                        if (raw === "") { setColsInput(raw); return; }
                        const num = parseInt(raw);
                        if (!isNaN(num)) {
                            const clamped = Math.max(1, Math.min(8, num));
                            setColsInput(String(clamped));
                            handleColsChange(clamped);
                        }
                    }}
                    onFocus={(e) => e.target.select()}
                    min={1}
                    max={8}
                    style={{ width: 60 }}
                />
            </Flex>

            <Flex direction="row" gap="sm" alignItems="center">
                <span>Overlap:</span>
                <Input
                    type="number"
                    value={overlap}
                    onChange={(e) => {
                        const val = parseFloat(e.target.value);
                        if (!isNaN(val)) {
                            setOverlap(Math.max(0, Math.min(0.99, val)));
                        }
                    }}
                    min={0}
                    max={0.99}
                    step={0.05}
                    style={{ width: 80 }}
                />
            </Flex>

            <Checkbox
                value={globalDetection}
                label="Global Detection (include full image)"
                onChange={() => setGlobalDetection(!globalDetection)}
            />

            <Flex direction="column" gap="sm">
                <GridMatrixEditor
                    rows={rows}
                    cols={cols}
                    matrix={gridMatrix}
                    selectedValue={selectedValue}
                    onCellClick={handleCellClick}
                />

                <Button
                    onClick={() => {
                        setGridMatrix(createDefaultMatrix(rows, cols));
                        setSelectedValue(null);
                    }}
                    disabled={!isGridModified}
                >
                    Reset Grid
                </Button>
            </Flex>

            <Button onClick={handleUpdate}>Update Tiling</Button>
        </Flex>
    );
}
