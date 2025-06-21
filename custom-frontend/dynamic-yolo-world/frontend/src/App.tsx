
import { css } from "../styled-system/css/css.mjs";
import { Streams, useConnection } from "@luxonis/depthai-viewer-common";
import { useState } from "react";
import { MessageInput } from "./MessageInput.tsx";
import { ConfidenceSlider } from "./ConfidenceSlider.tsx";

function App() {
    const connection = useConnection();
    const [selectedClasses, setSelectedClasses] = useState<string[]>(["person", "chair", "TV"]);
    const [confidence, setConfidence] = useState(0.1);

    const updateClasses = (input: string) => {
        const updated = input.split(',').map(c => c.trim()).filter(Boolean);
        console.log('Sending classes to backend:', updated);
        // Send to backend
        // @ts-ignore - Custom service
        connection.daiConnection?.postToService('Class Update Service', updated, (response) => {
            console.log('Backend acknowledged class update:', response);
            setSelectedClasses(updated);
        });
    };

    const updateConfidence = (value: number) => {
        console.log('Sending threshold to backend:', value);
        // Send to backend
        // @ts-ignore - Custom service
        connection.daiConnection?.postToService('Threshold Update Service', value, (response) => {
            console.log('Backend acknowledged threshold update:', response);
            setConfidence(value);
        });
    };


    return (
        <main className={css({
            width: 'screen',
            height: 'screen',
            display: 'flex',
            flexDirection: 'row',
            gap: 'md',
            padding: 'md'
        })}>
            {/* Left: Stream Viewer */}
            <div className={css({ flex: 1 })}>
                <Streams hideToolbar />
            </div>

            {/* Vertical Divider */}
            <div className={css({
                width: '2px',
                backgroundColor: 'gray.300'
            })} />

            {/* Right: Info and Control Column */}
            <div className={css({
                width: 'md',
                display: 'flex',
                flexDirection: 'column',
                gap: 'md'
            })}>
                <h1 className={css({ fontSize: '2xl', fontWeight: 'bold' })}>
                    Dynamic YOLO-World Example
                </h1>
                <p>This example showcases the integration of the YOLO-World model with a custom static frontend, enabling dynamic configuration of the object classes you want to detect at runtime.</p>

                <div>
                    <h3 className={css({ fontWeight: 'semibold', marginBottom: 'sm' })}>Selected Classes:</h3>
                    <ul className={css({ listStyleType: 'disc', paddingLeft: 'lg' })}>
                        {selectedClasses.map((cls, idx) => (
                            <li key={idx}>{cls}</li>
                        ))}
                    </ul>
                </div>

                <MessageInput onClassUpdate={updateClasses} />

                <ConfidenceSlider
                    initialValue={confidence}
                    onUpdate={updateConfidence}
                />

                {/* Connection Status at Bottom */}
                <div className={css({
                    display: 'flex',
                    alignItems: 'center',
                    gap: 'xs',
                    marginTop: 'auto',
                    color: connection.connected ? 'green.500' : 'red.500'
                })}>
                    <div className={css({
                        width: '3',
                        height: '3',
                        borderRadius: 'full',
                        backgroundColor: connection.connected ? 'green.500' : 'red.500'
                    })} />
                    <span>{connection.connected ? 'Connected to device' : 'Disconnected'}</span>
                </div>
            </div>
        </main>
    );
}

export default App;
