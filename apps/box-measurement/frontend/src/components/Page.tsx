import type { ReactNode } from "react";

import { Flex } from "@luxonis/common-fe-components";
import TopNav from "./TopNav";

type PageProps = {
    children: ReactNode;
};

function Page({ children }: PageProps) {
    return (
        <Flex direction="column" minH="100vh">
            <TopNav />
            <Flex direction="column" flex="1" p="md">
                <main>{children}</main>
            </Flex>
        </Flex>
    );
}

export default Page;
