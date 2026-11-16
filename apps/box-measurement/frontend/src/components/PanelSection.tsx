import type { ReactNode } from 'react';

type PanelSectionProps = {
	title: string;
	hint?: string;
	children: ReactNode;
};

// A titled group of controls in the right panel.
function PanelSection({ title, hint, children }: PanelSectionProps) {
	return (
		<section className="flex flex-col gap-3">
			<h2 className="mt-2 mb-1 text-base font-semibold">{title}</h2>
			{hint ? <p className="text-xs text-muted-foreground">{hint}</p> : null}
			{children}
		</section>
	);
}

export default PanelSection;
