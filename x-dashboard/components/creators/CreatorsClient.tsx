"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardFooter, CardHeader } from "@/components/ui/card";
import type { CreatorPersona, CreatorPersonaPost, CreatorPersonaRun } from "@/lib/db";

type CreatorItem = {
  persona: CreatorPersona;
  latestRun: CreatorPersonaRun | null;
  posts: CreatorPersonaPost[];
};

type Props = {
  items: CreatorItem[];
};

const MIN_WIDTH = 280;
const MAX_WIDTH = 520;

export function CreatorsClient({ items }: Props) {
  const [selectedHandle, setSelectedHandle] = useState<string | null>(
    items[0]?.persona.handle ?? null
  );
  const [itemState, setItemState] = useState(items);
  const [listWidth, setListWidth] = useState(360);
  const resizingRef = useRef<{ startX: number; startWidth: number } | null>(null);
  const [handleInput, setHandleInput] = useState("");
  const [running, setRunning] = useState(false);
  const [overwrite, setOverwrite] = useState(true);
  const router = useRouter();

  const selectedItem = useMemo(
    () => itemState.find((item) => item.persona.handle === selectedHandle) ?? null,
    [itemState, selectedHandle]
  );

  useEffect(() => {
    setItemState(items);
    if (!items.find((item) => item.persona.handle === selectedHandle)) {
      setSelectedHandle(items[0]?.persona.handle ?? null);
    }
  }, [items, selectedHandle]);

  useEffect(() => {
    function onPointerMove(event: PointerEvent) {
      if (!resizingRef.current) return;
      const delta = event.clientX - resizingRef.current.startX;
      const next = resizingRef.current.startWidth + delta;
      setListWidth(Math.min(MAX_WIDTH, Math.max(MIN_WIDTH, next)));
    }

    function onPointerUp() {
      resizingRef.current = null;
      window.removeEventListener("pointermove", onPointerMove);
      window.removeEventListener("pointerup", onPointerUp);
    }

    if (resizingRef.current) {
      window.addEventListener("pointermove", onPointerMove);
      window.addEventListener("pointerup", onPointerUp);
    }

    return () => {
      window.removeEventListener("pointermove", onPointerMove);
      window.removeEventListener("pointerup", onPointerUp);
    };
  }, [resizingRef.current]);

  function onResizeStart(event: React.PointerEvent<HTMLDivElement>) {
    resizingRef.current = { startX: event.clientX, startWidth: listWidth };
    (event.target as HTMLElement).setPointerCapture(event.pointerId);
  }

  async function togglePersona(handle: string, isActive: boolean) {
    const nextStatus = isActive ? "active" : "inactive";
    setItemState((prev) =>
      prev.map((item) =>
        item.persona.handle === handle
          ? { ...item, persona: { ...item.persona, status: nextStatus } }
          : item
      )
    );
    await fetch(`/api/creators/${handle}/status`, {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ status: nextStatus })
    });
  }

  async function runPersonaCapture() {
    if (!handleInput.trim()) return;
    setRunning(true);
    await fetch("/api/creators/run", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ handle: handleInput.trim(), force: overwrite })
    });
    setRunning(false);
    setHandleInput("");
    router.refresh();
  }

  async function deletePersona(handle: string) {
    const ok = window.confirm(`Delete @${handle}? This removes cached posts and runs.`);
    if (!ok) return;
    await fetch(`/api/creators/${handle}`, { method: "DELETE" });
    router.refresh();
  }

  return (
    <div className="flex h-[calc(100vh-7rem)] min-h-0 gap-4">
      <section
        className="space-y-4 overflow-y-auto pr-2"
        style={{ width: listWidth }}
      >
        <div>
          <h1 className="text-2xl font-semibold text-white">Creators</h1>
          <p className="text-sm text-slate-400">
            Cached personas and greatest hits
          </p>
        </div>

        <Card>
          <CardHeader className="space-y-1">
            <div className="text-sm font-semibold text-slate-200">Add creator</div>
            <div className="text-xs text-slate-400">Capture and cache their latest posts</div>
          </CardHeader>
          <CardContent className="space-y-2">
            <input
              className="w-full rounded-md border border-slate-700 bg-white px-3 py-2 text-sm text-slate-900"
              placeholder="@handle or handle"
              value={handleInput}
              onChange={(event) => setHandleInput(event.target.value)}
            />
            <label className="flex items-center gap-2 text-xs text-slate-400">
              <input
                type="checkbox"
                checked={overwrite}
                onChange={(event) => setOverwrite(event.target.checked)}
              />
              Overwrite if exists
            </label>
          </CardContent>
          <CardFooter className="flex justify-end">
            <Button onClick={runPersonaCapture} disabled={running || !handleInput.trim()}>
              {running ? "Capturing..." : "Capture Persona"}
            </Button>
          </CardFooter>
        </Card>

        <div className="space-y-3">
          {itemState.map((item) => {
            const isActive = item.persona.handle === selectedHandle;
            return (
              <Card
                key={item.persona.handle}
                className={isActive ? "border-blue-400" : "border-slate-800"}
              >
                <button
                  className="w-full text-left"
                  onClick={() => setSelectedHandle(item.persona.handle)}
                >
                  <CardHeader className="space-y-1">
                    <div className="flex items-center justify-between">
                      <div className="text-sm font-semibold text-slate-200">
                        @{item.persona.handle}
                      </div>
                      <div className="flex items-center gap-2">
                        <Badge>{item.persona.status}</Badge>
                        <label className="flex items-center gap-2 text-xs text-slate-400">
                          <input
                            type="checkbox"
                            checked={item.persona.status === "active"}
                            onClick={(event) => event.stopPropagation()}
                            onChange={(event) =>
                              togglePersona(item.persona.handle, event.target.checked)
                            }
                          />
                          Use
                        </label>
                      </div>
                    </div>
                    <div className="text-xs text-slate-400">
                      {item.persona.display_name || "Creator persona"}
                    </div>
                  </CardHeader>
                  <CardContent className="text-xs text-slate-400">
                    Latest run:{" "}
                    {item.latestRun?.run_at
                      ? new Date(item.latestRun.run_at).toLocaleString()
                      : "None"}
                  </CardContent>
                </button>
              </Card>
            );
          })}
        </div>
      </section>

      <div
        className="w-1 cursor-col-resize rounded-full bg-slate-800/70 hover:bg-slate-600/80"
        onPointerDown={onResizeStart}
        role="separator"
        aria-orientation="vertical"
      />

      <section className="flex-1 space-y-4 overflow-y-auto pr-2">
        {!selectedItem ? (
          <Card>
            <CardHeader>
              <div className="text-sm text-slate-200">Creator Persona</div>
            </CardHeader>
            <CardContent className="text-sm text-slate-400">
              No creator selected yet.
            </CardContent>
          </Card>
        ) : (
          <CreatorDetail
            item={selectedItem}
            onToggle={togglePersona}
            onDelete={deletePersona}
          />
        )}
      </section>
    </div>
  );
}

function CreatorDetail({
  item,
  onToggle,
  onDelete
}: {
  item: CreatorItem;
  onToggle: (handle: string, active: boolean) => void;
  onDelete: (handle: string) => void;
}) {
  const { persona, latestRun, posts } = item;
  return (
    <div className="space-y-4">
      <Card>
        <CardHeader className="space-y-1">
          <div className="text-lg font-semibold text-white">@{persona.handle}</div>
          <div className="text-xs text-slate-400">
            {persona.display_name || "Creator persona snapshot"}
          </div>
          <div className="flex flex-wrap items-center gap-2 text-xs text-slate-400">
            <Badge>{persona.status}</Badge>
            <label className="flex items-center gap-2 text-xs text-slate-400">
              <input
                type="checkbox"
                checked={persona.status === "active"}
                onChange={(event) => onToggle(persona.handle, event.target.checked)}
              />
              Use in workflow
            </label>
            <Link
              className="text-xs text-blue-300 underline"
              href={`https://x.com/${persona.handle}`}
              target="_blank"
            >
              View on X
            </Link>
          </div>
        </CardHeader>
        <CardContent className="space-y-2 text-sm text-slate-300">
          {latestRun?.summary_json ? (
            <pre className="whitespace-pre-wrap rounded-md bg-slate-900 p-3 text-xs text-slate-200">
              {JSON.stringify(latestRun.summary_json, null, 2)}
            </pre>
          ) : (
            <p>No summary found. Run the persona capture pipeline.</p>
          )}
          {latestRun?.output_md_path ? (
            <div className="text-xs text-slate-500">
              Cached summary: {latestRun.output_md_path}
            </div>
          ) : null}
        </CardContent>
        <CardFooter className="flex flex-wrap items-center justify-between gap-2 text-xs text-slate-400">
          <div>
            Latest run:{" "}
            {latestRun?.run_at ? new Date(latestRun.run_at).toLocaleString() : "None"}
          </div>
          <Button variant="destructive" onClick={() => onDelete(persona.handle)}>
            Delete Persona
          </Button>
        </CardFooter>
      </Card>

      <section className="space-y-3">
        <div>
          <h2 className="text-lg font-semibold text-white">Greatest Hits</h2>
          <p className="text-sm text-slate-400">Top posts by engagement score</p>
        </div>
        <div className="grid gap-4 lg:grid-cols-2">
          {posts.map((post) => (
            <Card key={post.id}>
              <CardHeader className="space-y-1">
                <div className="text-sm text-slate-300">
                  Score: {post.engagement_score ?? 0}
                </div>
                <div className="text-xs text-slate-500">{post.created_at}</div>
                {post.tweet_url ? (
                  <Link className="text-xs text-blue-300 underline" href={post.tweet_url} target="_blank">
                    View post
                  </Link>
                ) : null}
              </CardHeader>
              <CardContent className="text-sm text-slate-200">
                {post.content || "No content captured."}
              </CardContent>
            </Card>
          ))}
        </div>
      </section>
    </div>
  );
}
