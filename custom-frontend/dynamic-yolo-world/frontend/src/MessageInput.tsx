import { Flex, Button, Input } from "@luxonis/common-fe-components";
import { useRef } from "react";

interface MessageInputProps {
    onClassUpdate: (classes: string) => void;
}

export function MessageInput({ onClassUpdate }: MessageInputProps) {
    const inputRef = useRef<HTMLInputElement>(null);

    const handleSendMessage = () => {
        if (inputRef.current) {
            const value = inputRef.current.value;
            console.log('Sending new class list:', value);
            onClassUpdate(value);
            inputRef.current.value = '';
        }
    };

    return (
        <Flex direction="row" gap="sm" alignItems="center">
            <Input type="text" placeholder="person,chair,TV" ref={inputRef} />
            <Button onClick={handleSendMessage}>Update&nbsp;Classes</Button>
        </Flex>
    );
}
