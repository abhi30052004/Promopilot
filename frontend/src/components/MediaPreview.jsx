import React, { useState } from 'react';
import { ImageOff, LoaderCircle } from 'lucide-react';
import { resolveMediaUrl } from '../lib/media';
import { useLanguage } from '../lib/LanguageContext';

// Never renders a broken-image icon: unavailable media shows a labelled placeholder instead.
export default function MediaPreview({
  src,
  mediaType,
  status,
  alt = '',
  className = 'w-full h-full object-cover',
  controls = true,
  fallbackText,
}) {
  const { t } = useLanguage();
  const [failedSrc, setFailedSrc] = useState(null);
  const url = resolveMediaUrl(src);
  const processing = status === 'PENDING' || status === 'GENERATING' || status === 'PROCESSING';
  const failed = failedSrc === url;

  if (!url || failed || processing) {
    const text = fallbackText
      || (processing ? t('common.media_generating') : status === 'FAILED' ? t('common.media_failed') : t('common.media_unavailable'));
    return (
      <div className="w-full h-full min-h-24 flex flex-col items-center justify-center gap-2 bg-slate-100 text-slate-500 p-4 text-center">
        {processing ? <LoaderCircle className="animate-spin" size={24} /> : <ImageOff size={24} />}
        <span className="text-xs font-medium">{text}</span>
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
        preload="metadata"
        onError={() => setFailedSrc(url)}
      />
    );
  }

  return <img src={url} alt={alt} className={className} loading="lazy" onError={() => setFailedSrc(url)} />;
}
