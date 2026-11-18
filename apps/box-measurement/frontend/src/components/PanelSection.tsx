import { NormalText, SubLabel } from '@luxonis/ui-components';
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
			{/* The text components render spans; the h2 keeps the section heading. */}
			<h2 className="mt-2 mb-1">
				<NormalText weight="bold" text={title} />
			</h2>
			{hint ? <SubLabel text={hint} /> : null}
			{children}
		</section>
	);
}

export default PanelSection;
