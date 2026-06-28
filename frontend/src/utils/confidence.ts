export type ConfidenceTierName = 'green' | 'yellow' | 'red';

export interface ConfidenceTierInfo {
  tier: ConfidenceTierName;
  color: string;      // hex colour for react-konva stroke
  label: string;      // human-readable label
  tailwind: string;   // tailwind class for UI badges
}

const TIERS: Record<ConfidenceTierName, Omit<ConfidenceTierInfo, 'tier'>> = {
  green: {
    color: '#22c55e',
    label: 'High confidence',
    tailwind: 'text-green-500 bg-green-50 border-green-200',
  },
  yellow: {
    color: '#eab308',
    label: 'Medium confidence',
    tailwind: 'text-yellow-600 bg-yellow-50 border-yellow-200',
  },
  red: {
    color: '#ef4444',
    label: 'Low confidence',
    tailwind: 'text-red-500 bg-red-50 border-red-200',
  },
};

export function getConfidenceTier(confidence: number): ConfidenceTierInfo {
  let tierName: ConfidenceTierName;
  if (confidence > 0.95) {
    tierName = 'green';
  } else if (confidence >= 0.8) {
    tierName = 'yellow';
  } else {
    tierName = 'red';
  }
  return { tier: tierName, ...TIERS[tierName] };
}

export function getConfidenceColor(confidence: number): string {
  return getConfidenceTier(confidence).color;
}
