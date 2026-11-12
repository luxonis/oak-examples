import { Flex } from "@luxonis/common-fe-components";

import { css } from "../../styled-system/css/css.mjs";
import Page from "../components/Page";
import SettingsForm from "./SettingsForm";

function SettingsPage() {
    return (
        <Page>
            <Flex direction="column" width="full" alignItems="center">
                <div
                    className={css({
                        width: "100%",
                        maxWidth: "breakpoint-lg",
                    })}
                >
                    <SettingsForm />
                </div>
            </Flex>
        </Page>
    );
}

export default SettingsPage;
