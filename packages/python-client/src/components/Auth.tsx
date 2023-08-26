import { useEffect, useState } from 'react';
import {
  useWidgetModel,
  useWidgetModelState,
  useWidgetTransport,
} from '../lib/widget-model';
import Loader from './Loader';
import Button from './Button';

export default function Auth() {
  const [initiated, setInitiated] = useState(false);
  const [authUrl] = useWidgetModelState('auth_url');
  const [widgetState] = useWidgetModelState('auth_state');
  const model = useWidgetModel();
  const transport = useWidgetTransport();

  useEffect(() => {
    if (!initiated || authUrl || !model || widgetState !== 'needs-auth') {
      return;
    }

    async function load() {
      await transport('initiate-auth', {});
    }

    load();
  }, [initiated, authUrl, model, transport, widgetState]);

  useEffect(() => {
    if (!initiated || !authUrl || !model || widgetState !== 'auth-in-progress') {
      return;
    }
    window.open(authUrl, 'popup');
  }, [authUrl, model, transport, widgetState]);

  const cancelAuth = async () => {
    setInitiated(false);
    await transport('cancel-auth', {});
  };

  if (widgetState === 'authenticated') {
    return null;
  }

  return (
    <div className="lmk-flex lmk-items-center lmk-content-center lmk-h-full lmk-grow lmk-flex-col">
      {!initiated ? (
        <div className="lmk-flex lmk-m-2 lmk-flex-col lmk-items-center lmk-gap-4">
          Log in to LMK
          <Button onClick={() => setInitiated(true)}>
            Log in
          </Button>
        </div>
      ) : !authUrl ? (
        <div className="lmk-flex lmk-flex-col lmk-m-2 lmk-items-center lmk-gap-4">
          <Loader size={5} />
          <h2>Getting auth URL</h2>
          <Button onClick={cancelAuth}>
            Cancel
          </Button>
        </div>
      ) : (
        <div className="lmk-flex lmk-m-2 lmk-flex-col lmk-items-center lmk-gap-4">
          <Loader size={5} />
          <div className="lmk-flex lmk-flex-col lmk-items-center">
            <h2 className="lmk-m-0">Waiting for authentication</h2>
            <p className="lmk-m-0">A new window should open for you to authenticate with LMK.</p>
            <p className="lmk-m-0">If one does not open, you can manually navigate to:</p>
            <p className="lmk-m-0">
              <a href={authUrl || ''} target="_blank" className="lmk-link">
                {authUrl}
              </a>
            </p>
          </div>
          <Button onClick={cancelAuth}>
            Cancel
          </Button>
        </div>
      )}
    </div>
  );
}
