import { useState } from "react";
import { Key, Plus, Trash2, Fingerprint } from "lucide-react";
import { apiClient } from "@/shared/api/client";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";

interface Credential {
  id: string;
  device_name: string;
  created_at: string;
  last_used_at: string | null;
}

export function PasskeySettings() {
  const queryClient = useQueryClient();
  const [deviceName, setDeviceName] = useState("");
  const [isRegistering, setIsRegistering] = useState(false);

  const { data: credentials, isLoading } = useQuery({
    queryKey: ["webauthn-credentials"],
    queryFn: async () => {
      const resp = await apiClient.get<Credential[]>("/auth/webauthn/credentials");
      return resp.data;
    },
  });

  const deleteMutation = useMutation({
    mutationFn: async (credentialId: string) => {
      await apiClient.delete(`/auth/webauthn/credentials/${credentialId}`);
    },
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["webauthn-credentials"] }),
  });

  const handleRegister = async () => {
    setIsRegistering(true);
    try {
      // Step 1: Get challenge from server
      const beginResp = await apiClient.post<{
        challenge: string;
        rp: { name: string; id: string };
        user: { id: string; name: string; displayName: string };
        pub_key_cred_params: Array<{ type: string; alg: number }>;
        timeout: number;
        authenticator_selection: Record<string, unknown>;
      }>("/auth/webauthn/register/begin");

      const options = beginResp.data;

      // Step 2: Call WebAuthn API
      if (!window.PublicKeyCredential) {
        alert("WebAuthn is not supported in this browser");
        return;
      }

      const credential = await navigator.credentials.create({
        publicKey: {
          challenge: Uint8Array.from(atob(options.challenge.replace(/-/g, "+").replace(/_/g, "/")), (c) => c.charCodeAt(0)),
          rp: options.rp,
          user: {
            id: new TextEncoder().encode(options.user.id),
            name: options.user.name,
            displayName: options.user.displayName,
          },
          pubKeyCredParams: options.pub_key_cred_params.map((p) => ({
            type: p.type as PublicKeyCredentialType,
            alg: p.alg,
          })),
          timeout: options.timeout,
          authenticatorSelection: options.authenticator_selection as AuthenticatorSelectionCriteria,
        },
      }) as PublicKeyCredential | null;

      if (!credential) return;

      const response = credential.response as AuthenticatorAttestationResponse;

      // Step 3: Send credential to server
      await apiClient.post("/auth/webauthn/register/complete", {
        credential_id: btoa(String.fromCharCode(...new Uint8Array(credential.rawId))),
        client_data_json: btoa(String.fromCharCode(...new Uint8Array(response.clientDataJSON))),
        attestation_object: btoa(String.fromCharCode(...new Uint8Array(response.attestationObject))),
        device_name: deviceName || "My Passkey",
      });

      setDeviceName("");
      queryClient.invalidateQueries({ queryKey: ["webauthn-credentials"] });
    } catch (err) {
      console.error("WebAuthn registration failed:", err);
    } finally {
      setIsRegistering(false);
    }
  };

  return (
    <div className="space-y-6">
      <div>
        <h3 className="text-lg font-semibold" style={{ color: "var(--text-primary)" }}>
          Passkeys
        </h3>
        <p className="text-sm" style={{ color: "var(--text-secondary)" }}>
          Use biometric authentication or security keys for passwordless login
        </p>
      </div>

      {/* Register new passkey */}
      <div className="rounded-lg border p-4" style={{ borderColor: "var(--border-subtle)", background: "var(--bg-surface)" }}>
        <div className="flex items-end gap-3">
          <div className="flex-1">
            <label className="block text-sm font-medium mb-1" style={{ color: "var(--text-secondary)" }}>
              Device Name
            </label>
            <input
              type="text"
              value={deviceName}
              onChange={(e) => setDeviceName(e.target.value)}
              placeholder="e.g., MacBook Pro"
              className="w-full rounded-md border px-3 py-2 text-sm"
              style={{
                borderColor: "var(--border-default)",
                background: "var(--bg-base)",
                color: "var(--text-primary)",
              }}
            />
          </div>
          <button
            onClick={handleRegister}
            disabled={isRegistering}
            className="flex items-center gap-2 rounded-md px-4 py-2 text-sm font-medium transition-colors"
            style={{ background: "var(--brand-500)", color: "white" }}
          >
            <Plus className="h-4 w-4" />
            {isRegistering ? "Registering..." : "Add Passkey"}
          </button>
        </div>
      </div>

      {/* Existing credentials */}
      {isLoading ? (
        <div className="text-sm" style={{ color: "var(--text-secondary)" }}>Loading...</div>
      ) : !credentials?.length ? (
        <div className="rounded-lg border p-8 text-center" style={{ borderColor: "var(--border-subtle)", background: "var(--bg-surface)" }}>
          <Fingerprint className="mx-auto h-8 w-8 mb-2" style={{ color: "var(--text-tertiary)" }} />
          <p className="text-sm" style={{ color: "var(--text-secondary)" }}>No passkeys registered</p>
          <p className="text-xs mt-1" style={{ color: "var(--text-tertiary)" }}>
            Add a passkey to enable passwordless authentication
          </p>
        </div>
      ) : (
        <div className="space-y-2">
          {credentials.map((cred) => (
            <div
              key={cred.id}
              className="flex items-center gap-3 rounded-lg border p-3"
              style={{ borderColor: "var(--border-subtle)", background: "var(--bg-surface)" }}
            >
              <Key className="h-5 w-5 shrink-0" style={{ color: "var(--brand-400)" }} />
              <div className="flex-1">
                <p className="text-sm font-medium" style={{ color: "var(--text-primary)" }}>
                  {cred.device_name || "Unnamed Passkey"}
                </p>
                <p className="text-xs" style={{ color: "var(--text-tertiary)" }}>
                  Added {new Date(cred.created_at).toLocaleDateString()}
                  {cred.last_used_at && ` · Last used ${new Date(cred.last_used_at).toLocaleDateString()}`}
                </p>
              </div>
              <button
                onClick={() => deleteMutation.mutate(cred.id)}
                className="rounded-md p-2 transition-colors hover:bg-danger-500/10"
                style={{ color: "var(--danger-500)" }}
                title="Remove passkey"
              >
                <Trash2 className="h-4 w-4" />
              </button>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
