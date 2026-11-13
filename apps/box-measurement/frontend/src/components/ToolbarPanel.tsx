import { Button, type IconType, SubHeader } from '@luxonis/ui-components';
import { type ReactNode, useEffect, useId, useRef } from 'react';

type ToolbarPanelProps = {
	label: string;
	icon?: IconType;
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
	icon,
	open,
	onOpenChange,
	disabled = false,
	children,
}: ToolbarPanelProps) {
	const panelId = useId();
	const containerRef = useRef<HTMLDivElement>(null);
	const triggerRef = useRef<HTMLButtonElement>(null);

	useEffect(() => {
		if (!open) {
			return;
		}

		const onPointerDown = (event: PointerEvent) => {
			if (!containerRef.current?.contains(event.target as Node)) {
				onOpenChange(false);
			}
		};
		const onKeyDown = (event: KeyboardEvent) => {
			if (event.key === 'Escape') {
				onOpenChange(false);
				triggerRef.current?.focus();
			}
		};

		document.addEventListener('pointerdown', onPointerDown);
		document.addEventListener('keydown', onKeyDown);
		return () => {
			document.removeEventListener('pointerdown', onPointerDown);
			document.removeEventListener('keydown', onKeyDown);
		};
	}, [open, onOpenChange]);

	return (
		<div ref={containerRef} className="relative">
			<Button
				ref={triggerRef}
				type="button"
				variant={open ? 'filled' : 'outline'}
				icon={icon}
				label={label}
				aria-expanded={open}
				aria-controls={panelId}
				disabled={disabled}
				onClick={() => onOpenChange(!open)}
			/>
			{open ? (
				<section
					id={panelId}
					aria-label={label}
					className="absolute top-full right-0 z-20 mt-2 flex w-80 max-w-[calc(100vw-2rem)] flex-col gap-3 rounded-md border border-border bg-background p-4 text-left shadow-md"
				>
					<SubHeader text={label} />
					{children}
				</section>
			) : null}
		</div>
	);
}

export default ToolbarPanel;
