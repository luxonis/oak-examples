import { Flex, Button, Input } from "@luxonis/common-fe-components";
import { useRef, useState } from "react";
import { css } from "../styled-system/css/css.mjs";
import { useConnection } from "@luxonis/depthai-viewer-common";
import { useNotifications } from "./Notifications.tsx";

export function ClassSelector() {
    const inputRef = useRef<HTMLInputElement>(null);
    const connection = useConnection();
    const [selectedClasses, setSelectedClasses] = useState<string[]>(["person", "chair", "TV"]);
    const { notify } = useNotifications();

    const handleSendMessage = () => {
        if (inputRef.current) {
            const value = inputRef.current.value;
            const updatedClasses = value
                .split(',')
                .map((c: string) => c.trim())
                .filter(Boolean);

            if (updatedClasses.length === 0) {
                notify('Please enter at least one class (comma separated).', { type: 'warning', durationMs: 5000 });
                return;
            }
            if (!connection.connected) {
                notify('Not connected to device. Unable to update classes.', { type: 'error' });
                return;
            }

            console.log('Sending new class list to backend:', updatedClasses);
            notify(`Updating ${updatedClasses.length} class${updatedClasses.length > 1 ? 'es' : ''}…`, { type: 'info' });

            connection.daiConnection?.postToService(
                // @ts-ignore - Custom service
                "Class Update Service",
                updatedClasses,
                () => {
                    console.log('Backend acknowledged class update');
                    setSelectedClasses(updatedClasses);
                    notify(`Classes updated (${updatedClasses.join(', ')})`, { type: 'success', durationMs: 6000 });
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
                {selectedClasses.map((cls: string, idx: number) => (
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
