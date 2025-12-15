import { useEffect, useRef, useState } from "react";
import { useDaiConnection } from "@luxonis/depthai-viewer-common";

export type EmotionName =
  | "Happiness" | "Anger" | "Neutral" | "Sadness"
  | "Surprise"  | "Fear"  | "Disgust" | "Contempt";

export type FaceMeta = {
  id?: string;
  status?: "NEW" | "REID" | "TBD";
  age?: number;
  gender?: "Male" | "Female";
  emotion?: EmotionName;
  img_url?: string;                
};

export type FaceStats = {
  age: number;
  males: number;
  females: number;
  emotions: Partial<Record<EmotionName, number>>;
};

function shallowEqualFaces(a: (FaceMeta | undefined)[], b: (FaceMeta | undefined)[]) {
  if (a.length !== b.length) return false;
  for (let i = 0; i < a.length; i++) {
    const A = a[i], B = b[i];
    if (!A && !B) continue;
    if (!A || !B) return false;
    if (
      A.id      !== B.id      ||
      A.age     !== B.age     ||
      A.gender  !== B.gender  ||
      A.emotion !== B.emotion ||
      A.img_url !== B.img_url 
    ) return false;
  }
  return true;
}

export function useFacesPoll() {
  const { connected, daiConnection } = useDaiConnection();
  const [faces, setFaces] = useState<(FaceMeta | undefined)[]>([undefined, undefined, undefined]);
  const [stats, setStats] = useState<FaceStats | undefined>(undefined);

  const inFlight = useRef(false);
  const timer = useRef<number | null>(null);

  useEffect(() => {
    if (!connected) return;

    const tick = () => {
      if (inFlight.current || document.hidden) return;
      inFlight.current = true;

      // @ts-ignore custom service name
      daiConnection?.postToService("Get Faces", {}, (resp: any) => {
        const arr = Array.isArray(resp?.faces) ? resp.faces : [];
        const next: (FaceMeta | undefined)[] = [arr[0], arr[1], arr[2]];
        setFaces(prev => (shallowEqualFaces(prev, next) ? prev : next));
        if (resp?.stats) setStats(resp.stats);
        inFlight.current = false;
      });
    };

    const loop = () => {
      tick();
      timer.current = window.setTimeout(loop, 1000); // 1 Hz
    };

    loop();
    return () => {
      if (timer.current) clearTimeout(timer.current);
      inFlight.current = false;
    };
  }, [connected, daiConnection]);

  return { faces, stats };
}
