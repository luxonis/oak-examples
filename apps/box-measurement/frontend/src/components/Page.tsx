import { Header } from '@luxonis/ui-components';
import type { ReactNode } from 'react';

type PageProps = {
	children: ReactNode;
};

function Page({ children }: PageProps) {
	return (
		<div className="flex min-h-screen flex-col">
			<header className="flex items-center border-b border-border p-2">
				<Header text="Box Measurement" />
			</header>
			<main className="flex flex-1 flex-col p-4">{children}</main>
		</div>
	);
}

export default Page;
