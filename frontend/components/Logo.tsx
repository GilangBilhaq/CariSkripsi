export function Logo({ size = "md" }: { size?: "sm" | "md" | "xl" }) {
  const cls = { sm: "text-xl", md: "text-2xl", xl: "text-6xl sm:text-8xl" }[size];
  return (
    <span className={`font-serif leading-none ${cls}`}>
      <span className="text-ink">Cari</span>
      <span className="italic text-sbert">Skripsi</span>
    </span>
  );
}
