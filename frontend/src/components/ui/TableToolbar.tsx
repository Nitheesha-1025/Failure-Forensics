import type { ReactNode } from "react";

interface TableToolbarProps {
  searchValue: string;
  onSearchChange: (value: string) => void;
  placeholder?: string;
  children?: ReactNode;
}

export function TableToolbar({
  searchValue,
  onSearchChange,
  placeholder = "Filter by filename…",
  children,
}: TableToolbarProps) {
  return (
    <div className="table-toolbar">
      <label className="table-toolbar-search">
        <span className="visually-hidden">Filter table</span>
        <input
          type="search"
          value={searchValue}
          placeholder={placeholder}
          onChange={(e) => onSearchChange(e.target.value)}
        />
      </label>
      {children ? <div className="table-toolbar-actions">{children}</div> : null}
    </div>
  );
}
