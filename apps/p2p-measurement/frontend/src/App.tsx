import { css } from "../styled-system/css/css.mjs";
import { Streams, useDaiConnection } from "@luxonis/depthai-viewer-common";
import { ClickCatcher } from "./ClickOverlay.tsx";
import { useRef, useState, useEffect } from "react";
import { DistanceDisplay } from "./DistanceDisplay.tsx";

function App() {
    const connection = useDaiConnection();
    const viewerRef = useRef<HTMLDivElement>(null);
    const [pointCount, setPointCount] = useState(0);
    const [currentDistance, setCurrentDistance] = useState<number | null>(null);
    const [currentStdDeviation, setCurrentStdDeviation] = useState<number | null>(null);
    const [hasInvalidDepth, setHasInvalidDepth] = useState(false);
    const [trackingEnabled, setTrackingEnabled] = useState(true);
    const [showInstructions, setShowInstructions] = useState(false);

    const selectionService = "Selection Service";

    const clearSelection = () => {
        (connection as any)?.daiConnection?.postToService(selectionService, { clear: true });
        setPointCount(0);
        setCurrentDistance(null);
        setCurrentStdDeviation(null);
        setHasInvalidDepth(false);
    };

    const toggleTracking = () => {
        if (connection.daiConnection) {
            (connection.daiConnection as any).postToService(
                "Toggle Tracking Service",
                {},
                (response: any) => {
                    try {
                        let parsedResponse = response;
                        if (response && response.constructor && response.constructor.name === 'DataView') {
                            const decoder = new TextDecoder();
                            const jsonString = decoder.decode(response);
                            parsedResponse = JSON.parse(jsonString);
                        }
                        
                        if (parsedResponse?.ok) {
                            setTrackingEnabled(parsedResponse.tracking_enabled);
                        }
                    } catch (e) {
                        console.error('Error toggling tracking:', e);
                    }
                }
            );
        }
    };

    useEffect(() => {
        if (connection.connected) {
            const daiConnection = (connection as any)?.daiConnection;
            
            const pollDistance = () => {
                if (daiConnection && daiConnection.postToService) {
                    daiConnection.postToService(
                        "Get Distance Service",
                        {},
                        (response: any) => {
                            try {
                                let parsedResponse = response;
                                if (response && response.constructor && response.constructor.name === 'DataView') {
                                    const decoder = new TextDecoder();
                                    const jsonString = decoder.decode(response);
                                    parsedResponse = JSON.parse(jsonString);
                                }
                                
                                if (parsedResponse?.ok && parsedResponse.distance !== null && typeof parsedResponse.distance === 'number') {
                                    setCurrentDistance(parsedResponse.distance);
                                    setCurrentStdDeviation(parsedResponse.std_deviation || null);
                                    setHasInvalidDepth(parsedResponse.has_invalid_depth || false);
                                } else if (parsedResponse?.ok && parsedResponse.distance === null) {
                                    setCurrentDistance(null);
                                    setCurrentStdDeviation(null);
                                    setHasInvalidDepth(parsedResponse.has_invalid_depth || false);
                                }
                            } catch (e) {
                                console.error('Error parsing distance service response:', e);
                            }
                        }
                    );
                }
            };
            
            const interval = setInterval(pollDistance, 50); // 50ms polling
            
            return () => clearInterval(interval);
        }
    }, [connection.connected]);

    useEffect(() => {
        if (connection.connected && connection.daiConnection) {
            (connection.daiConnection as any).postToService(
                "Get Tracking Status Service",
                {},
                (response: any) => {
                    try {
                        let parsedResponse = response;
                        if (response && response.constructor && response.constructor.name === 'DataView') {
                            const decoder = new TextDecoder();
                            const jsonString = decoder.decode(response);
                            parsedResponse = JSON.parse(jsonString);
                        }
                        
                        if (parsedResponse?.ok) {
                            setTrackingEnabled(parsedResponse.tracking_enabled);
                        }
                    } catch (e) {
                        console.error('Error getting tracking status:', e);
                    }
                }
            );
        }
    }, [connection.connected, connection.daiConnection]);

    useEffect(() => {
        const handleKeyPress = (event: KeyboardEvent) => {
            if (event.code === 'Space' && pointCount > 0) {
                event.preventDefault();
                clearSelection();
            }
        };

        window.addEventListener('keydown', handleKeyPress);
        return () => window.removeEventListener('keydown', handleKeyPress);
    }, [pointCount]);

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
            <div ref={viewerRef} className={css({ flex: 1, position: "relative" })}>
                <Streams
                    defaultTopics={["Video", "Depth", "Point Annotations"]}
                    topicGroups={{ images: "Images", data: "Data" }}
                />
                <ClickCatcher
                    containerRef={viewerRef}
                    frameWidth={640}
                    frameHeight={400}
                    debug
                    allowedPanelTitle="Video,Depth"
                    serviceName={selectionService}
                    onPointAdded={(count) => {
                        if (count === -1) {
                            setPointCount(prev => {
                                const newCount = prev + 1;
                                return newCount;
                            });
                        } else {
                            setPointCount(count);
                        }
                    }}
                />
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
                <h1 className={css({ fontSize: 'xl', fontWeight: 'bold' })}>
                    P2P Distance Measurement
                </h1>
                
                <div className={css({
                    padding: 'sm',
                    backgroundColor: 'gray.50',
                    borderRadius: 'md',
                    border: '1px solid',
                    borderColor: 'gray.200',
                    marginBottom: 'sm'
                })}>
                    <button
                        className={css({
                            width: '100%',
                            display: 'flex',
                            justifyContent: 'space-between',
                            alignItems: 'center',
                            backgroundColor: 'transparent',
                            border: 'none',
                            cursor: 'pointer',
                            padding: '0',
                            marginBottom: showInstructions ? 'xs' : '0'
                        })}
                        onClick={() => setShowInstructions(!showInstructions)}
                    >
                        <h3 className={css({ 
                            fontWeight: 'semibold', 
                            margin: '0',
                            color: 'gray.800'
                        })}>
                            Instructions
                        </h3>
                        <span className={css({ 
                            fontSize: 'xs',
                            color: 'gray.500',
                            transform: showInstructions ? 'rotate(180deg)' : 'rotate(0deg)',
                            transition: 'transform 0.2s',
                            fontWeight: 'bold',
                            lineHeight: '1'
                        })}>
                            ▼
                        </span>
                    </button>
                    {showInstructions && (
                        <ol className={css({ 
                            listStyleType: 'decimal', 
                            paddingLeft: 'sm',
                            fontSize: 'sm',
                            lineHeight: 'relaxed',
                            color: 'gray.700',
                            margin: '0'
                        })}>
                            <li>Click on the video or depth stream to select the first point</li>
                            <li>Click again to select the second point</li>
                            <li>The distance will be calculated and displayed</li>
                            <li><strong>Wait a moment</strong> for the measurement to stabilize</li>
                            <li>Press <strong>Space</strong> or right-click to clear points and reset</li>
                            <li>Switch between Video and Depth views using the tabs</li>
                        </ol>
                    )}
                </div>

                {/* Distance Display */}
                <DistanceDisplay 
                    distance={currentDistance} 
                    stdDeviation={currentStdDeviation}
                    pointCount={pointCount}
                    hasInvalidDepth={hasInvalidDepth}
                    trackingEnabled={trackingEnabled}
                    onToggleTracking={toggleTracking}
                />

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
