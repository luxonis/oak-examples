import { Flex, Button, Input } from "@luxonis/common-fe-components";
import { useRef, useState } from "react";
import { css } from "../styled-system/css/css.mjs";
import { useConnection } from "@luxonis/depthai-viewer-common";

export function ClassSelector() {
    const inputRef = useRef<HTMLInputElement>(null);
    const connection = useConnection();
    const [selectedClasses, setSelectedClasses] = useState<string[]>(["person", "chair", "TV"]);

    const handleSendMessage = () => {
        if (inputRef.current) {
            const value = inputRef.current.value;
            const updatedClasses = value
                .split(',')
                .map(c => c.trim())
                .filter(Boolean);

            console.log('Sending new class list to backend:', updatedClasses);

            connection.daiConnection?.postToService(
                // @ts-ignore - Custom service
                "Class Update Service",
                updatedClasses,
                () => {
                    console.log('Backend acknowledged class update');
                    setSelectedClasses(updatedClasses);
                }
            );

            inputRef.current.value = '';
        }
    };

    return (
        <div className={css({ display: 'flex', flexDirection: 'column', gap: 'sm' })}>
            {/* Class List Display */}
            <h3 className={css({ fontWeight: "semibold" })}>Update Classes with Text Input:</h3>
            <ul className={css({ listStyleType: 'disc', paddingLeft: 'lg' })}>
                {selectedClasses.map((cls, idx) => (
                    <li key={idx}>{cls}</li>
                ))}
            </ul>

            
            {/* Input + Button */}
            <Flex direction="row" gap="sm" alignItems="center">
                <Input type="text" placeholder="person,chair,TV" ref={inputRef} />
                <Button onClick={handleSendMessage}>Update&nbsp;Classes</Button>
            </Flex>
        </div>
    );
}
