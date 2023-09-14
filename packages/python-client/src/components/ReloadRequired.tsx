
export type ReloadRequiredContext = 'colab';

export interface ReloadRequiredProps {
  context: ReloadRequiredContext;
}

export default function ReloadRequired({ context }: ReloadRequiredProps) {
  return (
    <div className="lmk-flex lmk-items-center lmk-content-center lmk-h-full lmk-grow lmk-flex-col">
      <div className="lmk-flex lmk-m-2 lmk-flex-col lmk-items-center lmk-gap-4 lmk-max-w-[400px]">
        <span>
          <b>Widget reload required</b>
        </span>
        {context === 'colab' ? (
          <span className="lmk-text-center">
            Due to limitations of the Google Colab platform, you must re-execute this cell
            to continue using the LMK widget.
          </span>
        ) : null}
        <span className="lmk-text-center">
          You can still monitor this notebook remotely and configure notification preferences
          via the <a href="https://app.lmkapp.dev" className="lmk-link" target="_blank">the LMK app</a>.
        </span>
      </div>
    </div>
  );
}
