import { SkillEditor } from "@/components/skills/SkillEditor";
import { getSkillBySlug } from "@/lib/db";

type Props = {
  params: { slug: string };
};

export default function SkillDetailPage({ params }: Props) {
  const skill = getSkillBySlug(params.slug);
  if (!skill) {
    return (
      <div className="text-sm text-slate-300">
        Skill not found. Return to /skills.
      </div>
    );
  }
  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-semibold text-white">Skill Detail</h1>
        <p className="text-sm text-slate-400">Edit config and save back to SQLite</p>
      </div>
      <SkillEditor skill={skill} />
    </div>
  );
}
