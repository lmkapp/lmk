import { useEffect } from 'react';
import { useWidgetModelState } from '../lib/widget-model';
import Auth from './Auth';
import Layout from './Layout';
import WidgetContent from './WidgetContent';

import '../../styles/tailwind.css';

export default function Widget() {
  const [widgetState] = useWidgetModelState('auth_state');
  const [url, setUrl] = useWidgetModelState('url');
  const windowUndefined = typeof window === 'undefined';

  useEffect(() => {
    const ivl = setInterval(() => {
      if (windowUndefined) {
        return;
      }
      if (url === window.location.href) {
        return;
      }
      setUrl(window.location.href);
    }, 1000);

    return () => clearInterval(ivl);
  }, [url, windowUndefined]);

  return (
    <Layout>
      {widgetState === 'authenticated' ? <WidgetContent /> : <Auth />}
    </Layout>
  );
}
