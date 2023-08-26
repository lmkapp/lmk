import '../../styles/Loader.css';

export interface LoaderProps {
  size?: number;
}

export default function Loader({ size }: LoaderProps) {
  return (
    <div style={{ width: size && size * 8, height: size && size * 8 }}>
      <div
        className="jp-lmk-Loader"
        style={{ fontSize: size, marginTop: size && size * 3.5 }}
      />
    </div>
  );
}
