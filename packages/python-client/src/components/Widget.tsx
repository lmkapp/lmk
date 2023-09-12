import { useState } from 'react';
import { useColabSupport } from '../hooks/colab';
import { useKeepUrlUpdated } from '../hooks/url';
import { useWidgetModelState } from '../lib/widget-model';
import Auth from './Auth';
import Layout from './Layout';
import WidgetContent from './WidgetContent';

import '../../styles/tailwind.css';

export default function Widget() {
  const [requiresReload, setRequiresReload] = useState(false);
  const [widgetState] = useWidgetModelState('auth_state');

  useColabSupport({ setRequiresReload });
  useKeepUrlUpdated();

  return (
    <Layout>
      {requiresReload ? (
        <p>Reload required</p> 
      ) : widgetState === 'authenticated' ? (
        <WidgetContent /> 
      ) : (
        <Auth />
      )}
    </Layout>
  );
}
