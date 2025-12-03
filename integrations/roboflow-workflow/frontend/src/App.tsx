import { css } from "../styled-system/css/css.mjs";
import { Streams, useConnection } from "@luxonis/depthai-viewer-common";
import { MessageInput } from "./MessageInput.tsx";

function App() {
  const connection = useConnection();

  return (
    <main
      className={css({
        width: 'screen',
        height: 'screen',
        display: 'flex',
        flexDirection: 'row',
        gap: 'md',
        padding: 'md'
      })}
    >
        {/* Left: Stream Viewer */}
        <div className={css({ flex: 1, position: 'relative' })}>
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
                Roboflow Workflow & DepthAI Integration Example
            </h1>
            <p>
                Simple application showing integration between <b>DepthAI cameras</b> and <b>Roboflow Workflow</b> through 
                the Inference package. Live video is streamed from the camera, processed through your Roboflow 
                workflow on the device, and both predictions and visualizations are rendered in the DepthAI Visualizer.
            </p>

            <ul className={css({ listStyleType: 'disc', paddingLeft: 'md'})}>
                <li>To switch the displayed stream, click the <b>X</b> icon and select another source.</li>
                <li>To toggle detection overlays on or off, use the <b>filter icon</b> at the top.</li>
            </ul>
            
            {/* Message Input Form */}
            <MessageInput />
            
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
