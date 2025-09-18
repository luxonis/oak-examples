import { css } from "../styled-system/css/css.mjs";
import { Streams, useConnection } from "@luxonis/depthai-viewer-common";
import { ClassSelector } from "./ClassSelector.tsx";
import { ConfidenceSlider } from "./ConfidenceSlider.tsx";
import { ImageUploader } from "./ImageUploader.tsx";

function App() {
    const connection = useConnection();

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
                <Streams />
            </div>

            {/* Vertical Divider */}
            <div className={css({
                width: '2px',
                backgroundColor: 'gray.300'
            })} />

            {/* Right: Sidebar (Info and Controls) */}
            <div className={css({
                width: 'md',
                display: 'flex',
                flexDirection: 'column',
                gap: 'md'
            })}>
                <h1 className={css({ fontSize: '2xl', fontWeight: 'bold' })}>
                    Dynamic YOLO-World/YOLOE Example
                </h1>
                <p>
                    This example showcases the integration of the YOLO-World/YOLOE model with a custom static frontend,
                    enabling dynamic configuration of the object classes you want to detect at runtime.
                </p>

                {/* Class Input */}
                <ClassSelector />

                {/* Image Uploader */}
                <ImageUploader />

                {/* Confidence Slider */}
                <ConfidenceSlider initialValue={0.1} />

                {/* Connection Status */}
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
