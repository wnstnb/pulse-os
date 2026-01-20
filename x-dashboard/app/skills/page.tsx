import Link from "next/link";

import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader } from "@/components/ui/card";
import { getSkills } from "@/lib/db";

export default function SkillsPage() {
  const skills = getSkills();

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-semibold text-white">Skills</h1>
        <p className="text-sm text-slate-400">Manage skill definitions and priorities</p>
      </div>

      <div className="grid gap-4 lg:grid-cols-2">
        {skills.map((skill) => (
          <Card key={skill.slug}>
            <CardHeader className="flex flex-row items-center justify-between">
              <div>
                <div className="text-lg font-semibold text-white">{skill.name}</div>
                <div className="text-xs text-slate-400">{skill.slug}</div>
              </div>
              <Badge>{skill.status}</Badge>
            </CardHeader>
            <CardContent className="space-y-2 text-sm text-slate-300">
              <div>Type: {skill.type}</div>
              <div>Priority: {skill.priority}</div>
              <Link className="text-xs text-blue-300 underline" href={`/skills/${skill.slug}`}>
                View & edit
              </Link>
            </CardContent>
          </Card>
        ))}
      </div>
    </div>
  );
}
