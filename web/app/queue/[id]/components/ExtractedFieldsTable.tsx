"use client";
import { useState } from "react";
import { Edit3 } from "lucide-react";
import type { ExtractedField } from "@/lib/api";
import { humaniseFieldName } from "./rules";

interface ExtractedFieldsTableProps {
  fields: ExtractedField[];
  overrides: Record<string, string>;
  onOverride: (fieldName: string, value: string) => void;
  onRevert: (fieldName: string) => void;
  activeField: string | null;
  onActiveFieldChange: (fieldName: string | null) => void;
  /** Overrides form part of a review decision, so they lock while one submits. */
  disabled?: boolean;
}

/** What the pipeline read off the package, and the corrections a reviewer made. */
export function ExtractedFieldsTable({
  fields,
  overrides,
  onOverride,
  onRevert,
  activeField,
  onActiveFieldChange,
  disabled = false,
}: ExtractedFieldsTableProps) {
  const [editingField, setEditingField] = useState<string | null>(null);
  const [draft, setDraft] = useState("");

  const startEdit = (field: ExtractedField) => {
    setEditingField(field.field_name);
    setDraft(overrides[field.field_name] ?? field.raw_text ?? "");
  };

  const commit = (fieldName: string) => {
    onOverride(fieldName, draft);
    setEditingField(null);
  };

  if (fields.length === 0) {
    return (
      <p className="font-body text-sm text-ink-600">
        No fields were extracted from this capture. If calibration failed, the pipeline stopped
        before it could read the label.
      </p>
    );
  }

  return (
    <div className="overflow-x-auto">
      <table className="data-table">
        <caption className="sr-only">Extracted label fields and reviewer corrections</caption>
        <thead>
          <tr>
            <th scope="col">Field</th>
            <th scope="col">Text read from the label</th>
            <th scope="col">Confidence</th>
            <th scope="col">Height</th>
            <th scope="col" className="text-right">
              Action
            </th>
          </tr>
        </thead>
        <tbody>
          {fields.map((field) => {
            const isEditing = editingField === field.field_name;
            const isOverridden = field.field_name in overrides;
            const value = isOverridden ? overrides[field.field_name] : field.raw_text ?? "—";

            return (
              <tr
                key={field.id}
                className={activeField === field.field_name ? "bg-brass-500/10" : ""}
                onMouseEnter={() => onActiveFieldChange(field.field_name)}
                onMouseLeave={() => onActiveFieldChange(null)}
              >
                <th scope="row" className="px-3 py-2 text-left">
                  <span className="font-body text-xs font-semibold uppercase tracking-wider text-ink-900">
                    {humaniseFieldName(field.field_name)}
                  </span>
                </th>

                <td className="w-1/2">
                  {isEditing ? (
                    <div className="flex items-center gap-2">
                      <label className="sr-only" htmlFor={`override-${field.id}`}>
                        Corrected text for {humaniseFieldName(field.field_name)}
                      </label>
                      <input
                        id={`override-${field.id}`}
                        type="text"
                        value={draft}
                        onChange={(e) => setDraft(e.target.value)}
                        className="form-input min-h-[36px] py-1 text-xs"
                        autoFocus
                      />
                      <button
                        type="button"
                        onClick={() => commit(field.field_name)}
                        className="btn-primary min-h-[36px] px-3 py-1 text-xs"
                      >
                        Save
                      </button>
                      <button
                        type="button"
                        onClick={() => setEditingField(null)}
                        className="btn-secondary min-h-[36px] px-3 py-1 text-xs"
                      >
                        Cancel
                      </button>
                    </div>
                  ) : (
                    <div className="flex items-center gap-2">
                      <span className="font-mono text-xs text-ink-900">{value}</span>
                      {isOverridden && (
                        <span className="rounded bg-brass-500/15 px-1.5 py-0.5 font-mono text-[10px] font-semibold text-brass-500">
                          CORRECTED
                        </span>
                      )}
                    </div>
                  )}
                </td>

                <td>
                  <span className="font-mono text-xs text-ink-900">
                    {field.ocr_confidence !== null
                      ? `${Math.round(field.ocr_confidence * 100)}%`
                      : "—"}
                  </span>
                </td>

                <td>
                  <span className="font-mono text-xs text-ink-900">
                    {field.font_height_mm !== null ? `${field.font_height_mm.toFixed(1)} mm` : "—"}
                  </span>
                </td>

                <td className="text-right">
                  {isOverridden ? (
                    <button
                      type="button"
                      onClick={() => onRevert(field.field_name)}
                      disabled={disabled}
                      className="font-body text-xs text-ink-600 underline hover:text-ink-900 disabled:opacity-40"
                    >
                      Revert
                    </button>
                  ) : (
                    !isEditing && (
                      <button
                        type="button"
                        onClick={() => startEdit(field)}
                        disabled={disabled}
                        className="inline-flex items-center gap-1 text-xs font-semibold text-brass-500 transition-colors hover:text-ink-900 disabled:opacity-40"
                      >
                        <Edit3 size={13} aria-hidden />
                        Correct
                      </button>
                    )
                  )}
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}
