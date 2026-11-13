import { Header } from '@luxonis/ui-components';
import type { ReactNode } from 'react';

type PageProps = {
	children: ReactNode;
};

function Page({ children }: PageProps) {
	return (
		<div className="flex min-h-screen flex-col">
			<header className="flex items-center border-b border-border px-4 py-2">
				<h1>
					<Header text="Box Measurement" />
				</h1>
			</header>
			<main className="flex flex-1 flex-col p-4">{children}</main>
		</div>
	);
}

export default Page;
