"use client";

import { useState } from "react";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardFooter, CardHeader } from "@/components/ui/card";
import { Textarea } from "@/components/ui/textarea";
import type { Skill } from "@/lib/db";

type Props = {
  skill: Skill;
};

export function SkillEditor({ skill }: Props) {
  const [configText, setConfigText] = useState(
    JSON.stringify(skill.config_json, null, 2)
  );
  const [status, setStatus] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);

  async function saveConfig() {
    setSaving(true);
    setStatus(null);
    try {
      const parsed = JSON.parse(configText);
      const res = await fetch(`/api/skills/${skill.slug}`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ config_json: parsed })
      });
      if (!res.ok) {
        throw new Error("Failed to save skill");
      }
      setStatus("Saved");
    } catch (error) {
      setStatus("Invalid JSON or save failed");
    } finally {
      setSaving(false);
    }
  }

  return (
    <Card>
      <CardHeader>
        <div className="text-lg font-semibold text-white">{skill.name}</div>
        <div className="text-xs text-slate-400">{skill.slug}</div>
      </CardHeader>
      <CardContent className="space-y-3 text-sm text-slate-300">
        <div>Type: {skill.type}</div>
        <div>Status: {skill.status}</div>
        <div>Priority: {skill.priority}</div>
        <Textarea value={configText} onChange={(event) => setConfigText(event.target.value)} />
        {status ? <div className="text-xs text-slate-400">{status}</div> : null}
      </CardContent>
      <CardFooter>
        <Button onClick={saveConfig} disabled={saving}>
          Save Changes
        </Button>
      </CardFooter>
    </Card>
  );
}
