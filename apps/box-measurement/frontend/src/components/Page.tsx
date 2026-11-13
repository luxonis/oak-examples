import type { ReactNode } from 'react';

import { Flex, Header } from '@luxonis/common-fe-components';

type PageProps = {
	children: ReactNode;
};

function Page({ children }: PageProps) {
	return (
		<Flex direction="column" minH="100vh">
			<Flex p="xs" alignItems="center" borderBottom="border.base">
				<Header text="Box Measurement" />
			</Flex>
			<Flex direction="column" flex="1" p="md">
				<main>{children}</main>
			</Flex>
		</Flex>
	);
}

export default Page;
