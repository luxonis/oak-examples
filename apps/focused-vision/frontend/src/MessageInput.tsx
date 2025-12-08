import {Flex, Button, Input} from "@luxonis/common-fe-components";
import {useRef} from "react";
import {useDaiConnection} from "@luxonis/depthai-viewer-common";

export function MessageInput() {
    const connection = useDaiConnection();
    const inputRef = useRef<HTMLInputElement>(null);

    const handleSendMessage = () => {
        if (inputRef.current) {
            const message = inputRef.current.value;

            console.log('Sending message:', message);
            // @ts-ignore - We're using an example service here which isn't part of the DAI services enum
            connection.daiConnection?.postToService('Custom Service', message, (response) => {
                console.log('Received response:', response);
            });

            inputRef.current.value = '';
        }
    }

    return (
        <Flex direction="row" gap="sm" alignItems="center">
            <Input type="text" placeholder="Message" ref={inputRef}  />

            <Button onClick={handleSendMessage}>Send</Button>
        </Flex>
    );
}