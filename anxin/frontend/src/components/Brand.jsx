export default function Brand({ className = '' }) {
  return (
    <span className={`brand-wordmark ${className}`} aria-label="安芯">
      <span className="brand-an" aria-hidden="true">
        <svg className="brand-heart" viewBox="0 0 100 100" focusable="false">
          <path d="M50 28C60 28 72 14 82 14C92 14 100 28 94 44C88 60 64 88 50 88C36 88 12 60 6 44C0 28 8 14 18 14C28 14 40 28 50 28Z" />
        </svg>
        安
      </span>
      <span className="brand-xin" aria-hidden="true">芯</span>
    </span>
  )
}
