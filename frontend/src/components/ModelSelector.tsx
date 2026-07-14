interface Props {
  models: string[];
  selected: string;
  onChange: (model: string) => void;
  loading: boolean;
}

export default function ModelSelector({ models, selected, onChange, loading }: Props) {
  return (
    <select
      value={selected}
      onChange={(e) => onChange(e.target.value)}
      disabled={loading || models.length === 0}
      className="bg-bubble text-sm text-neutral-100 rounded-lg px-3 py-1.5
                 border border-white/10 outline-none focus:border-white/30
                 disabled:opacity-50 cursor-pointer"
    >
      {loading && <option>Loading…</option>}
      {!loading && models.length === 0 && <option>No models found</option>}
      {models.map((m) => (
        <option key={m} value={m}>
          {m}
        </option>
      ))}
    </select>
  );
}
