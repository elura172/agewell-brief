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
    description: "The physical, metabolic, and neural foundations that maintain daily vigor, sharp cognition, and physical autonomy.",
    question: "How do we keep the human vessel resilient, strong, and thriving throughout life?",
    status: "established",
    categories: ["brain health", "gut health", "metabolic health", "mobility", "sleep health", "general wellness"]
  },
  {
    slug: "regenerative-health",
    name: "Regenerative health",
    shortName: "Regeneration",
    description: "Mitochondrial dynamics, senolytic cell clearing, NRF-2 antioxidant activation, and epigenetic renewal.",
    question: "How do living tissues clean house, evict senescent cells, and reboot endogenous repair?",
    status: "emerging",
    categories: ["cellular senescence", "longevity", "detoxification", "metabolic health"]
  },
  {
    slug: "quantum-biology",
    name: "Quantum biology",
    shortName: "Quantum biology",
    description: "The frontier where subatomic quantum tunneling, electron transport, magnetoreception, and living systems meet.",
    question: "How do quantum phenomena govern enzyme catalysis, neural processing, and energy transfer inside living cells?",
    status: "emerging",
    categories: ["cellular senescence", "longevity", "brain health", "metabolic health"]
  },
  {
    slug: "vibrational-regenerative-health",
    name: "Vibrational & biophotonic health",
    shortName: "Vibration & light",
    description: "Biophoton emissions (Fritz-Albert Popp), structured cellular water, electromagnetic signaling, and living matrix coherence.",
    question: "How do light and electromagnetic frequencies coordinate signaling across 37 trillion cells simultaneously?",
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
