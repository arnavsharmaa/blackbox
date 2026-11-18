"use client";

import { useState } from "react";
import type { IncidentNote } from "@blackbox/schemas";
import { addNote, deleteNote } from "@/lib/api";
import { formatDateTime } from "@/lib/format";
import { Panel } from "@/components/ui";

/**
 * The incident's investigation scratchpad: what the operator said, what
 * was found on the floor, ticket links — unstructured, timestamped, and
 * carried through backup/restore with the incident.
 */
export function NotesPanel({
  incidentId,
  initialNotes,
}: {
  incidentId: string;
  initialNotes: IncidentNote[];
}) {
  const [notes, setNotes] = useState<IncidentNote[]>(initialNotes);
  const [text, setText] = useState("");
  const [author, setAuthor] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const submit = async () => {
    if (!text.trim() || busy) return;
    setBusy(true);
    setError(null);
    try {
      const note = await addNote(incidentId, {
        text: text.trim(),
        author: author.trim() || undefined,
      });
      setNotes((current) => [...current, note]);
      setText("");
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setBusy(false);
    }
  };

  const remove = async (noteId: number) => {
    try {
      await deleteNote(incidentId, noteId);
      setNotes((current) => current.filter((n) => n.id !== noteId));
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    }
  };

  return (
    <Panel title={`Notes${notes.length ? ` (${notes.length})` : ""}`}>
      {notes.length === 0 && (
        <p className="text-sm text-ink-faint">
          No notes yet — keep what you learn with the incident.
        </p>
      )}
      <ul className="space-y-2.5">
        {notes.map((note) => (
          <li key={note.id} className="group text-sm">
            <p className="whitespace-pre-wrap">{note.text}</p>
            <p className="mt-0.5 text-xs text-ink-faint">
              {note.author && <span>{note.author} · </span>}
              {formatDateTime(note.created_at)}
              <button
                type="button"
                onClick={() => remove(note.id)}
                aria-label={`Delete note ${note.id}`}
                className="ml-2 hidden text-red-300 hover:text-red-200 group-hover:inline"
              >
                delete
              </button>
            </p>
          </li>
        ))}
      </ul>
      <div className="mt-3 space-y-2 border-t border-edge/60 pt-3">
        <textarea
          value={text}
          onChange={(e) => setText(e.target.value)}
          rows={2}
          placeholder="Add an investigation note…"
          aria-label="New note"
          className="w-full rounded border border-edge bg-surface-2 px-2 py-1.5 text-sm focus:border-accent"
        />
        <div className="flex items-center gap-2">
          <input
            type="text"
            value={author}
            onChange={(e) => setAuthor(e.target.value)}
            placeholder="Your name (optional)"
            aria-label="Note author"
            className="flex-1 rounded border border-edge bg-surface-2 px-2 py-1 text-xs focus:border-accent"
          />
          <button
            type="button"
            onClick={submit}
            disabled={!text.trim() || busy}
            className="rounded border border-edge-strong bg-surface-2 px-3 py-1 text-sm hover:border-accent disabled:opacity-40"
          >
            {busy ? "Saving…" : "Add note"}
          </button>
        </div>
      </div>
      {error && (
        <p role="alert" className="mt-2 text-xs text-red-300">
          {error}
        </p>
      )}
    </Panel>
  );
}
