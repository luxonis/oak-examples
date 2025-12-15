import { Flex, Button, Input } from "@luxonis/common-fe-components";
import { useRef, useState, useEffect } from "react";
import { css } from "../../../styled-system/css/css.mjs";
import { useDaiConnection } from "@luxonis/depthai-viewer-common";
import { useToast } from "@luxonis/common-fe-components";

interface ClassSelectorProps {
    initialClasses?: string[];
}

export function ClassSelector({ initialClasses }: ClassSelectorProps) {
    const inputRef = useRef<HTMLInputElement>(null);
    const connection = useDaiConnection();
    const [selectedClasses, setSelectedClasses] = useState<string[]>(["person", "chair", "TV"]);
    const { toast } = useToast();

    // Update classes from backend config
    useEffect(() => {
        if (initialClasses && Array.isArray(initialClasses) && initialClasses.length > 0) {
            console.log("[ClassSelector] Restoring classes from backend:", initialClasses);
            setSelectedClasses([...initialClasses]); // Create new array to ensure update
        }
    }, [initialClasses]);

    const handleSendMessage = () => {
        if (inputRef.current) {
            const value = inputRef.current.value;
            const updatedClasses = value
                .split(',')
                .map((c: string) => c.trim())
                .filter(Boolean);

            if (updatedClasses.length === 0) {
                toast({
                    description: "Please enter at least one class (comma separated).",
                    colorVariant: "warning",
                    duration: "long",
                });                
                return;
            }
            if (!connection.connected) {
                toast({
                    description: "Not connected to device. Unable to update classes.",
                    colorVariant: "error",
                    duration: "default",
                });
                return;
            }

            console.log('Sending new class list to backend:', updatedClasses);
            toast({
                description: `Updating ${updatedClasses.length} class${
                    updatedClasses.length > 1 ? "es" : ""
                }…`,
                colorVariant: "gray",
                duration: "default",
            });

            connection.daiConnection?.postToService(
                // @ts-ignore - Custom service
                "Class Update Service",
                { classes : updatedClasses },
                () => {
                    console.log('Backend acknowledged class update');
                    setSelectedClasses(updatedClasses);
                toast({
                    description: `Classes updated (${updatedClasses.join(", ")})`,
                    colorVariant: "success",
                    duration: "long",
                    });                
                },
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
