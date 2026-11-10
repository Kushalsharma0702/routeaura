const COLORS = ['#2563eb', '#16a34a', '#dc2626', '#9333ea', '#ea580c', '#0891b2'];
export const dayColor = (day: number) => COLORS[(day - 1) % COLORS.length];
