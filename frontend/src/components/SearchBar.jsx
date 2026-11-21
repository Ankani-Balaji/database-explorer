export default function SearchBar({ value, onChange, placeholder = "Search..." }) {
  return (
    <input className="search" type="search" value={value} placeholder={placeholder}
      onChange={(e) => onChange(e.target.value)} />
  );
}
