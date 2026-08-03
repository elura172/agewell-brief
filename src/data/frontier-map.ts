export type FrontierStatus = "established" | "emerging" | "contested" | "historical" | "speculative";

export interface FrontierTerritory {
  slug: string;
  name: string;
  shortName: string;
  description: string;
  question: string;
  status: FrontierStatus;
  categories: string[];
}

export const frontierTerritories: FrontierTerritory[] = [
  {
    slug: "functional-health",
    name: "Functional health",
    shortName: "Function",
    description: "The everyday systems that help a person remain capable, steady, curious, and independent.",
    question: "What keeps the body useful in the world it actually lives in?",
    status: "established",
    categories: ["brain health", "gut health", "metabolic health", "mobility", "sleep health", "general wellness"]
  },
  {
    slug: "regenerative-health",
    name: "Regenerative health",
    shortName: "Regeneration",
    description: "Research on repair, resilience, senescence, mitochondrial function, epigenetics, and healthspan.",
    question: "How does the body repair, adapt, and recover over time?",
    status: "emerging",
    categories: ["cellular senescence", "longevity", "detoxification", "metabolic health"]
  },
  {
    slug: "quantum-biology",
    name: "Quantum biology",
    shortName: "Quantum biology",
    description: "The frontier where quantum processes, molecular biology, light, energy transfer, and living systems meet.",
    question: "Which quantum effects can be measured in living systems, and what might they explain?",
    status: "emerging",
    categories: ["cellular senescence", "longevity", "brain health", "metabolic health"]
  },
  {
    slug: "vibrational-regenerative-health",
    name: "Vibrational and biophotonic health",
    shortName: "Vibration",
    description: "A historical and emerging field of inquiry into biophotons, coherence, frequency, water, sound, and biological signaling.",
    question: "What signals travel through a living system, and how confidently can we measure them?",
    status: "contested",
    categories: ["general wellness", "cellular senescence", "detoxification", "brain health"]
  }
];

export const frontierStatusLabels: Record<FrontierStatus, string> = {
  established: "Established foundations",
  emerging: "Emerging evidence",
  contested: "Contested frontier",
  historical: "Historical vector",
  speculative: "Open hypothesis"
};

export function frontierForCategory(category: string): FrontierTerritory[] {
  const normalized = category.toLowerCase();
  return frontierTerritories.filter((territory) => territory.categories.includes(normalized));
}
