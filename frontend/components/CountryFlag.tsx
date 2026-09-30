// Kutu başlığında boydan boya uzanan bayraklar. Başlık yüksekliği sabit (72px) olduğundan
// yatay şeritler yüzdeyle, kanton ve yıldız pikselle çizilir; her genişlikte oranı bozulmaz.

const GR_BLUE = "#0d5eaf";
const IL_BLUE = "#0038b8";

function GreekFlag() {
  return (
    <>
      {Array.from({ length: 9 }, (_, i) => (
        <rect key={i} x="0" y={`${(i * 100) / 9}%`} width="100%" height={`${100 / 9 + 0.1}%`} fill={i % 2 ? "#fff" : GR_BLUE} />
      ))}
      {/* Kanton: beş şerit yüksekliğinde kare, beyaz haç */}
      <svg x="0" y="0" width="40" height="40" viewBox="0 0 10 10">
        <rect width="10" height="10" fill={GR_BLUE} />
        <rect x="4" width="2" height="10" fill="#fff" />
        <rect y="4" width="10" height="2" fill="#fff" />
      </svg>
    </>
  );
}

function IsraeliFlag() {
  const r = 14;
  const h = (r * Math.sqrt(3)) / 2;
  const up = `0,${-r} ${h},${r / 2} ${-h},${r / 2}`;
  const down = `0,${r} ${h},${-r / 2} ${-h},${-r / 2}`;
  return (
    <>
      <rect width="100%" height="100%" fill="#fff" />
      <rect y="9.4%" width="100%" height="15.6%" fill={IL_BLUE} />
      <rect y="75%" width="100%" height="15.6%" fill={IL_BLUE} />
      <svg x="50%" y="50%" overflow="visible">
        <polygon points={up} fill="none" stroke={IL_BLUE} strokeWidth="2.6" />
        <polygon points={down} fill="none" stroke={IL_BLUE} strokeWidth="2.6" />
      </svg>
    </>
  );
}

export default function CountryFlag({ country }: { country: string }) {
  return (
    <svg className="card-flag" aria-hidden="true" width="100%" height="100%">
      {country === "GR" ? <GreekFlag /> : country === "IL" ? <IsraeliFlag /> : null}
    </svg>
  );
}
