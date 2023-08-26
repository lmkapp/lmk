import { DOMWidgetModel, ISerializers } from "@jupyter-widgets/base";
import { createModelContext } from "../hooks/model";
import { MODULE_NAME, MODULE_VERSION } from "../version";
import { useCallback } from "react";

export interface NotificationChannel {
  notificationChannelId: string;
  name: string;
  order: number;
  isDefault: boolean;
  payload: any;
  createdAt: string;
  lastUpdatedAt: string;
}

export interface Notification {
  eventId: string;
  channels: {
    notificationChannelId: string;
    type: "email" | "text-message";
    name: string;
  }[];
}

export interface ILMKModel {
  url: string | null;
  notebook_name: string | null;
  auth_state:
    | "needs-auth"
    | "auth-in-progress"
    | "auth-error"
    | "authenticated";
  auth_url: string | null;
  access_token: string | null;
  api_url: string | null;
  session: any;
  jupyter_state: "idle" | "running" | null;
  jupyter_execution_num: number | null;
  jupyter_cell_state: "running" | "error" | "success" | "cancelled" | null;
  jupyter_cell_started_at: number | null;
  jupyter_cell_finished_at: number | null;
  jupyter_cell_error: string | null;
  monitoring_state: "none" | "error" | "stop";
  notify_min_execution: number | null;
  notify_min_time: number | null;
  channels_state: "none" | "loading" | "forbidden" | "loaded" | "error";
  selected_channel: string | null;
  channels: NotificationChannel[];
  sent_notifications: Notification[];
}

export const {
  Provider: WidgetViewProvider,
  useModel: useWidgetModel,
  useModelEvent: useWidgetModelEvent,
  useModelState: useWidgetModelState,
  useTransport: useWidgetTransport,
} = createModelContext<ILMKModel>();

export function useMonitoringState(): [
  ILMKModel["monitoring_state"],
  (state: ILMKModel["monitoring_state"]) => Promise<void>
] {
  const [monitoringState, setMonitoringState] =
    useWidgetModelState("monitoring_state");
  const setNotifyMinExecution = useWidgetModelState("notify_min_execution")[1];
  const setNotifyMinTime = useWidgetModelState("notify_min_time")[1];
  const [jupyterExecutionNum] = useWidgetModelState("jupyter_execution_num");
  const [apiUrl] = useWidgetModelState("api_url");
  const [session] = useWidgetModelState("session");
  const [accessToken] = useWidgetModelState("access_token");
  const [jupyterCellState] = useWidgetModelState("jupyter_cell_state");

  const setState = useCallback(
    async (event: ILMKModel["monitoring_state"]) => {
      setMonitoringState(event);
      setNotifyMinTime(Date.now());
      setNotifyMinExecution(jupyterExecutionNum);

      if (!session || !accessToken) {
        return;
      }

      if (jupyterCellState === "running") {
        // This is so that the UI updates while a cell is still running. Otherwise,
        // all changes get queued until the end of the cell and callbacks don't run,
        // so the new state is not transmitted to the backend. This is a bit of a workaround
        // but there doesn't seem to be any way to handle iopub events while a cell is still
        // running. I put enough hours into messing around w/ this for right now.
        const response = await fetch(
          `${apiUrl}/v1/session/${session.sessionId}`,
          {
            method: "PATCH",
            headers: {
              Authorization: `Bearer ${accessToken}`,
              "Content-Type": "application/json",
            },
            body: JSON.stringify({
              state: {
                notifyOn: event,
              },
            }),
          }
        );
        if (response.status !== 200) {
          console.error(
            `Error updating session: ${
              response.status
            }: ${await response.text()}`
          );
        }
      }
    },
    [jupyterCellState, apiUrl, session?.sessionId]
  );

  return [monitoringState, setState];
}

export function useSelectedChannel(): [
  string | null,
  (value: string | null) => Promise<void>
] {
  const [apiUrl] = useWidgetModelState("api_url");
  const [session] = useWidgetModelState("session");
  const [accessToken] = useWidgetModelState("access_token");
  const [jupyterCellState] = useWidgetModelState("jupyter_cell_state");
  const [selectedChannel, setSelectedChannel] =
    useWidgetModelState("selected_channel");

  const setState = useCallback(
    async (channelId: string | null) => {
      setSelectedChannel(channelId);

      if (!session || !accessToken) {
        return;
      }

      if (jupyterCellState === "running") {
        // See comment in useMonitoringState() for explanation
        const response = await fetch(
          `${apiUrl}/v1/session/${session.sessionId}`,
          {
            method: "PATCH",
            headers: {
              Authorization: `Bearer ${accessToken}`,
              "Content-Type": "application/json",
            },
            body: JSON.stringify({
              state: {
                notifyChannel: channelId,
              },
            }),
          }
        );
        if (response.status !== 200) {
          console.error(
            `Error updating session: ${
              response.status
            }: ${await response.text()}`
          );
        }
      }
    },
    [jupyterCellState, apiUrl, session?.sessionId]
  );

  return [selectedChannel, setState];
}

const defaultModelProperties: ILMKModel = {
  auth_state: "needs-auth",
  url: null,
  notebook_name: null,
  auth_url: null,
  access_token: null,
  api_url: null,
  jupyter_state: null,
  jupyter_execution_num: null,
  jupyter_cell_state: null,
  jupyter_cell_started_at: null,
  jupyter_cell_finished_at: null,
  jupyter_cell_error: null,
  session: null,
  monitoring_state: "none",
  notify_min_execution: null,
  notify_min_time: null,
  channels_state: "none",
  channels: [],
  selected_channel: null,
  sent_notifications: [],
};

export class LMKModel extends DOMWidgetModel {
  defaults() {
    return {
      ...super.defaults(),
      _model_name: LMKModel.model_name,
      _model_module: LMKModel.model_module,
      _model_module_version: LMKModel.model_module_version,
      _view_name: LMKModel.view_name,
      _view_module: LMKModel.view_module,
      _view_module_version: LMKModel.view_module_version,
      ...defaultModelProperties,
    };
  }

  static serializers: ISerializers = {
    ...DOMWidgetModel.serializers,
    // Add any extra serializers here
  };

  static model_name = "LMKModel";
  static model_module = MODULE_NAME;
  static model_module_version = MODULE_VERSION;
  static view_name = "LMKView"; // Set to null if no view
  static view_module = MODULE_NAME; // Set to null if no view
  static view_module_version = MODULE_VERSION;
}
