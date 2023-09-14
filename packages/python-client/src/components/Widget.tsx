import { useState } from 'react';
import { useColabSupport } from '../hooks/colab';
import { useKeepUrlUpdated } from '../hooks/url';
import { useWidgetModelState } from '../lib/widget-model';
import Auth from './Auth';
import Layout from './Layout';
import WidgetContent from './WidgetContent';

import '../../styles/tailwind.css';
import ReloadRequired, { ReloadRequiredContext } from './ReloadRequired';

export default function Widget() {
  const [requiresReload, setRequiresReload] = useState<ReloadRequiredContext>();
  const [widgetState] = useWidgetModelState('auth_state');
  let watchUrl = true;

  watchUrl &&= useColabSupport({
    requiresReload: requiresReload === 'colab',
    setRequiresReload: () => setRequiresReload('colab')
  });

  useKeepUrlUpdated(watchUrl);

  return (
    <Layout>
      {requiresReload !== undefined ? (
        <ReloadRequired context={requiresReload} />
      ) : widgetState === 'authenticated' ? (
        <WidgetContent /> 
      ) : (
        <Auth />
      )}
    </Layout>
  );
}
