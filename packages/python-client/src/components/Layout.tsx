export interface LayoutProps {
  children?: React.ReactNode;
}

export default function Layout({ children }: LayoutProps) {
  return (
    <div className="lmk-w-full lmk-min-h-[100px] lmk-font-jupyter lmk-text-font lmk-py-2 lmk-px-0 lmk-flex lmk-flex-col lmk-items-stretch [&>a]:lmk-text-link [&>a]:lmk-no-underline">
      {/* <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.1.1/css/all.min.css" /> */}
      {children}
    </div>
  );
}
