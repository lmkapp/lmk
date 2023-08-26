import cx from 'classnames';
import { FontAwesomeIcon } from '@fortawesome/react-fontawesome'
import { faArrowsRotate, faBars, faArrowRightFromBracket } from '@fortawesome/free-solid-svg-icons'
import { useEffect, useState } from 'react';
import { useClickOutside } from '../hooks/click-outside';
import { useWidgetTransport, useWidgetModelState, useSelectedChannel } from '../lib/widget-model';

export interface ChannelsProps {
  className?: string;
}

function Channels({ className }: ChannelsProps) {
  const transport = useWidgetTransport();
  const [channelState] = useWidgetModelState('channels_state');
  const [channels] = useWidgetModelState('channels');
  const [selectedChannel, setSelectedChannel] = useSelectedChannel();
  
  const loadChannels = async () => {
    await transport('refresh-channels', {});
  };

  useEffect(() => {
    if (channelState !== 'none') {
      return;
    }
    loadChannels();
  }, [transport, channelState]);

  return (
    <div className={`${className} lmk-flex-row lmk-gap-1 lmk-items-center lmk-flex`}>
      <p>
        <b>Notify:</b>
      </p>
      <div>
        {channelState === 'none' || channelState === 'loading' ? (
          <select className="lmk-bg-transparent">
            <option>Loading...</option>
          </select>
        ) : channelState === 'forbidden' || channelState === 'error' ? (
          <select className="lmk-bg-transparent">
            <option>Default</option>
          </select>
        ) : channels.length === 0 ? (
          <select className="lmk-bg-transparent">
            <option>No Channels Available</option>
          </select>
        ) : (
          <select
            className="lmk-bg-transparent"
            value={selectedChannel ?? undefined}
            onChange={async (evt) => {
              await setSelectedChannel(evt.target.value);
            }}
          >
            {channels.map((channel) => (
              <option
                key={channel.notificationChannelId}
                value={channel.notificationChannelId}
              >
                {channel.name} (
                {channel.payload.type === 'email'
                  ? channel.payload.emailAddress
                  : channel.payload.phoneNumber}
                )
              </option>
            ))}
          </select>
        )}
      </div>
    </div>
  );
}

export default function Navbar() {
  const transport = useWidgetTransport();
  const [menuExpanded, setMenuExpanded] = useState(false);
  const ref = useClickOutside<HTMLDivElement>(menuExpanded, () => setMenuExpanded(false));
  const [channelState] = useWidgetModelState('channels_state');

  const loadChannels = async () => {
    await transport('refresh-channels', {});
  };

  return (
    <div className="lmk-h-[24px] lmk-grid lmk-grid-cols-[max-content_1fr_auto_1fr_max-content] [&h3]:lmk-m-0 lmk-items-center">
      <h3 className="lmk-font-bold lmk-text-lg">LMK</h3>
      <Channels className="lmk-hidden lg:lmk-flex lmk-col-start-3" />
      <div className="lmk-col-start-5" ref={ref}>
        <div>
          <button
            type="button"
            id="lmkSettingsDropdownButton"
            aria-expanded="true"
            aria-haspopup="true"
            onClick={() => setMenuExpanded(!menuExpanded)}
          >
            <FontAwesomeIcon
              icon={faBars}
              className="lmk-cursor-pointer lmk-text-lg lmk-w-5 lmk-h-5"
            />
          </button>
        </div>
        <div
          id="lmkSettingsDropdown"
          className={cx(
            "lmk-absolute lmk-right-0 lmk-z-10 lmk-mt-2 lg:lmk-mr-1 lmk-w-full lg:lmk-w-56 lmk-origin-top-right lmk-rounded-md lmk-bg-white lmk-shadow-lg lmk-ring-1 lmk-ring-bgLight lmk-ring-opacity-5 lmk-bg-cellBg",
            { 'lmk-hidden': !menuExpanded }
          )}
          role="menu"
          aria-orientation="vertical"
          aria-labelledby="lmkSettingsDropdownButton"
          tabIndex={-1}
        >
          <div className="lmk-py-1 lmk-flex lmk-flex-col lmk-items-stretch" role="none">
            <div
              className="lmk-px-4 lmk-py-2 lmk-text-sm hover:lmk-bg-bgLight lmk-flex lmk-flex-row lmk-items-center lg:lmk-hidden"
              role="menuitem"
              tabIndex={-1}
            >
              <Channels />
            </div>
            <a
              href="#"
              className={cx(
                "lmk-px-4 lmk-py-2 lmk-text-sm hover:lmk-bg-bgLight lmk-flex lmk-flex-row lmk-items-center lmk-gap-2",
                channelState === 'loading' ? 'lmk-cursor-progress' : 'lmk-cursor-pointer'
              )}
              role="menuitem"
              tabIndex={-1}
              onClick={channelState === 'loading' ? undefined : (evt) => loadChannels()}
            >
              <span title="Refresh channels">
                <FontAwesomeIcon className="lmk-w-6" icon={faArrowsRotate}/>
              </span>
              <span>
                Refresh Channels
              </span>
            </a>
            <a
              href="#"
              className="lmk-px-4 lmk-py-2 lmk-text-sm hover:lmk-bg-bgLight lmk-flex lmk-flex-row lmk-items-center lmk-gap-2"
              role="menuitem"
              tabIndex={-1}
              onClick={async (evt) => {
                await transport('initiate-auth', { force: true });
              }}
            >
              <span title="Refresh channels">
                <FontAwesomeIcon icon={faArrowRightFromBracket} className="lmk-w-6"/>
              </span>
              <span>
                Re-Authenticate
              </span>
            </a>
          </div>
        </div>
      </div>
    </div>
  );
}
