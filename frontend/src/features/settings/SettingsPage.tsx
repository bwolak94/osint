import { useEffect } from "react";
import { useForm } from "react-hook-form";
import { useSettings, useUpdateSettings } from "./hooks";
import type { UpdateSettingsRequest } from "./types";
import { Button } from "@/shared/components/Button";
import { Input } from "@/shared/components/Input";
import { LoadingSpinner } from "@/shared/components/LoadingSpinner";

export function SettingsPage() {
  const { data: settings, isLoading } = useSettings();
  const updateMutation = useUpdateSettings();

  const { register, handleSubmit, reset } = useForm<UpdateSettingsRequest>();

  // Populate form when settings load
  useEffect(() => {
    if (settings) {
      reset({
        username: settings.username,
        notifications_enabled: settings.notifications_enabled,
        theme: settings.theme,
      });
    }
  }, [settings, reset]);

  const onSubmit = (data: UpdateSettingsRequest) => {
    updateMutation.mutate(data);
  };

  if (isLoading) return <LoadingSpinner />;

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-bold text-white">Settings</h1>

      <form
        onSubmit={handleSubmit(onSubmit)}
        className="max-w-lg space-y-6 rounded-lg border border-gray-800 bg-gray-900 p-6"
      >
        <Input label="Email" value={settings?.email ?? ""} disabled />
        <Input label="Username" {...register("username")} />

        <div className="flex items-center gap-3">
          <input
            type="checkbox"
            id="notifications"
            className="h-4 w-4 rounded border-gray-600 bg-gray-800"
            {...register("notifications_enabled")}
          />
          <label htmlFor="notifications" className="text-sm text-gray-300">
            Enable notifications
          </label>
        </div>

        <div>
          <label className="mb-1 block text-sm font-medium text-gray-300">
            Theme
          </label>
          <select
            className="w-full rounded-md border border-gray-700 bg-gray-800 px-3 py-2 text-gray-100"
            {...register("theme")}
          >
            <option value="dark">Dark</option>
            <option value="light">Light</option>
          </select>
        </div>

        {updateMutation.isSuccess && (
          <p className="text-sm text-green-400">Settings saved successfully.</p>
        )}

        <Button type="submit" disabled={updateMutation.isPending}>
          {updateMutation.isPending ? "Saving..." : "Save Settings"}
        </Button>
      </form>
    </div>
  );
}
