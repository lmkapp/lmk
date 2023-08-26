import ms from "ms";
import { useEffect, useState } from "react";

export interface TimeDeltaProps {
  since: Date;
  min?: number;
}

export default function TimeDelta({ since, min }: TimeDeltaProps) {
  const [now, setNow] = useState(new Date());

  let delta = now.getTime() - since.getTime();
  if (min !== undefined && delta < min) {
    delta = min;
  }

  useEffect(() => {
    let ivl: number;
    if (delta < 10000) {
      ivl = 1000;      
    } else if (delta < 60000) {
      ivl = 3000;
    } else if (delta < 60 * 60000) {
      ivl = 10000;
    } else {
      ivl = 60000;
    }

    setTimeout(() => {
      setNow(new Date());
    }, ivl);
  }, [now, since]);

  return <>{ms(delta)}</>;
}
