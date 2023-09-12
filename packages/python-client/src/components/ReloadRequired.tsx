
export type ReloadRequiredContext = 'colab';

export interface ReloadRequiredProps {
  context: ReloadRequiredContext;
}

export default function ReloadRequired({ context }: ReloadRequiredProps) {
  return <p>Reload required ({context})</p>
}
