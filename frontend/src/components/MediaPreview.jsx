import React, { useState } from 'react';
import { ImageOff, LoaderCircle } from 'lucide-react';
import { resolveMediaUrl } from '../lib/media';

export default function MediaPreview({
  src,
  mediaType,
  status,
  alt = '',
  className = 'w-full h-full object-cover',
  controls = true,
  fallbackText,
}) {
  const [failed, setFailed] = useState(false);
  const url = resolveMediaUrl(src);
  const processing = status === 'PENDING' || status === 'GENERATING' || status === 'PROCESSING';

  if (!url || failed || processing) {
    return (
      <div className="w-full h-full min-h-24 flex flex-col items-center justify-center gap-2 bg-slate-100 text-slate-500 p-4 text-center">
        {processing ? <LoaderCircle className="animate-spin" size={24} /> : <ImageOff size={24} />}
        <span className="text-xs font-medium">
          {fallbackText || (processing ? 'Generating media…' : 'Image unavailable — generating replacement')}
        </span>
      </div>
    );
  }

  if (mediaType === 'VIDEO') {
    return (
      <video
        src={url}
        className={className}
        controls={controls}
        playsInline
        muted
        onError={() => setFailed(true)}
      />
    );
  }

  return <img src={url} alt={alt} className={className} onError={() => setFailed(true)} />;
}
