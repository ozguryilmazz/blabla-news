"use client";

import { useState } from "react";

// Görsel kaynak sitede duruyor; açılmazsa (engel, silinmiş) alan tamamen gizlenir
export default function NewsImage({ src, className }: { src: string | null; className?: string }) {
  const [failed, setFailed] = useState(false);
  if (!src || failed) return null;
  return (
    // eslint-disable-next-line @next/next/no-img-element
    <img src={src} alt="" className={className} loading="lazy" referrerPolicy="no-referrer" onError={() => setFailed(true)} />
  );
}
