import { useEffect, useState } from 'react';
import { subscribeLoading } from '../lib/api';

// Thin animated bar at the top of the screen while any API request is in flight.
export default function TopProgress() {
  const [active, setActive] = useState(false);
  useEffect(() => subscribeLoading(setActive), []);
  if (!active) return null;
  return (
    <div className="fixed inset-x-0 top-0 z-[120] h-1 overflow-hidden bg-indigo-100" role="progressbar" aria-busy="true">
      <div className="h-full w-1/3 animate-[progress_1.1s_ease-in-out_infinite] rounded-full bg-indigo-600" />
    </div>
  );
}
