import { CreatorsClient } from "@/components/creators/CreatorsClient";
import {
  getCreatorPersonaPosts,
  getCreatorPersonas,
  getLatestCreatorPersonaRun
} from "@/lib/db";

export default function CreatorPersonasPage() {
  const personas = getCreatorPersonas();
  const items = personas.map((persona) => ({
    persona,
    latestRun: getLatestCreatorPersonaRun(persona.handle),
    posts: getCreatorPersonaPosts(persona.id, 10)
  }));

  return <CreatorsClient items={items} />;
}
