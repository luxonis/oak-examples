import { ArrowDownIcon, Button, SubHeader } from '@luxonis/ui-components';
import { type ReactNode, useEffect, useId, useRef } from 'react';

type ToolbarPanelProps = {
	label: string;
	open: boolean;
	onOpenChange: (open: boolean) => void;
	disabled?: boolean;
	children: ReactNode;
};

// A toolbar button that drops a settings panel below itself.
// ui-components has no popover, so this keeps the stream visible while the
// operator changes a setting, and closes on Escape or a click outside.
function ToolbarPanel({
	label,
	open,
	onOpenChange,
	disabled = false,
	children,
}: ToolbarPanelProps) {
	const panelId = useId();
	const headingId = useId();
	const containerRef = useRef<HTMLDivElement>(null);
	const triggerRef = useRef<HTMLButtonElement>(null);
	// Callers pass inline callbacks; a ref keeps the document listeners from
	// being re-added on every render.
	const onOpenChangeRef = useRef(onOpenChange);
	useEffect(() => {
		onOpenChangeRef.current = onOpenChange;
	});

	useEffect(() => {
		if (!open) {
			return;
		}

		const onPointerDown = (event: PointerEvent) => {
			if (!containerRef.current?.contains(event.target as Node)) {
				onOpenChangeRef.current(false);
			}
		};
		const onKeyDown = (event: KeyboardEvent) => {
			if (event.key === 'Escape') {
				onOpenChangeRef.current(false);
				triggerRef.current?.focus();
			}
		};

		document.addEventListener('pointerdown', onPointerDown);
		document.addEventListener('keydown', onKeyDown);
		return () => {
			document.removeEventListener('pointerdown', onPointerDown);
			document.removeEventListener('keydown', onKeyDown);
		};
	}, [open]);

	return (
		// Below the sm breakpoint the panel anchors to the nearest positioned
		// ancestor (the toolbar row) and spans its width, so a trigger near the
		// left edge cannot push the panel off screen.
		<div ref={containerRef} className="sm:relative">
			<Button
				ref={triggerRef}
				type="button"
				variant={open ? 'filled' : 'outline'}
				icon={ArrowDownIcon}
				iconPosition="end"
				label={label}
				aria-expanded={open}
				aria-controls={panelId}
				disabled={disabled}
				onClick={() => onOpenChange(!open)}
			/>
			{open ? (
				<section
					id={panelId}
					aria-labelledby={headingId}
					className="absolute top-full right-0 z-20 mt-2 flex w-80 max-w-[calc(100vw-2rem)] flex-col gap-3 rounded-md border border-border bg-background p-4 text-left shadow-md max-sm:left-0 max-sm:w-auto max-sm:max-w-none"
				>
					<h2 id={headingId}>
						<SubHeader text={label} />
					</h2>
					{children}
				</section>
			) : null}
		</div>
	);
}

export default ToolbarPanel;
