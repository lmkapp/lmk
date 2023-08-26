
export interface ButtonProps {
  onClick?: () => void;
  children?: React.ReactNode;
}

export default function Button({
  onClick,
  children,
}: ButtonProps) {
  return (
    <button onClick={onClick} className="lmk-border-editorBorder lmk-border-solid lmk-border lmk-rounded lmk-px-2 lmk-py-1 hover:lmk-bg-cellBg">
      {children}
    </button>
  );
}
