import { useState } from "react";
import {
  AlertTriangle,
  CheckCircle2,
  ChevronDown,
  ChevronRight,
  Info,
  Loader2,
  MonitorSmartphone,
  Radio,
  RefreshCw,
  ShieldAlert,
  Wifi,
  WifiOff,
  XCircle,
  Zap,
} from "lucide-react";
import {
  useDeauth,
  useHardwareStatus,
  useScanClients,
  useScanNetworks,
  useSetInterfaceMode,
} from "./hooks";
import type { AccessPoint } from "./types";

// ─── Signal bar helper ────────────────────────────────────────────────────────
function SignalBars({ dbm }: { dbm: number | null }) {
  if (dbm === null) return <span className="text-gray-500 text-xs">N/A</span>;
  const bars = dbm > -50 ? 4 : dbm > -65 ? 3 : dbm > -75 ? 2 : 1;
  return (
    <span className="flex items-end gap-0.5">
      {[1, 2, 3, 4].map((b) => (
        <span
          key={b}
          className={`inline-block w-1 rounded-sm ${
            b <= bars ? "bg-green-400" : "bg-gray-600"
          }`}
          style={{ height: `${b * 4}px` }}
        />
      ))}
      <span className="text-xs text-gray-400 ml-1">{dbm} dBm</span>
    </span>
  );
}

// ─── Encryption badge ─────────────────────────────────────────────────────────
function EncBadge({ enc }: { enc: string | null }) {
  const color =
    !enc || enc === "Open"
      ? "bg-red-500/20 text-red-400"
      : enc === "WEP"
      ? "bg-orange-500/20 text-orange-400"
      : enc.startsWith("WPA3")
      ? "bg-green-500/20 text-green-400"
      : "bg-yellow-500/20 text-yellow-400";
  return (
    <span className={`text-xs px-2 py-0.5 rounded-full font-mono ${color}`}>
      {enc ?? "Open"}
    </span>
  );
}

// ─── Tutorial section ─────────────────────────────────────────────────────────
const TUTORIAL_STEPS = [
  {
    icon: MonitorSmartphone,
    title: "1. Hardware Requirements",
    content: (
      <ul className="text-sm text-gray-300 space-y-1 list-disc list-inside">
        <li>Linux-based host (container or bare-metal)</li>
        <li>WiFi adapter with monitor mode support (Alfa AWUS036ACH, TP-Link TL-WN722N v1, Panda PAU09…)</li>
        <li>Root / CAP_NET_ADMIN + CAP_NET_RAW privileges</li>
        <li>
          Container flags:{" "}
          <code className="bg-gray-800 px-1 rounded text-xs">
            --privileged --cap-add=NET_ADMIN,NET_RAW
          </code>
        </li>
        <li>
          System tools:{" "}
          <code className="bg-gray-800 px-1 rounded text-xs">
            iwconfig iwlist tcpdump
          </code>{" "}
          (apt install wireless-tools tcpdump)
        </li>
      </ul>
    ),
  },
  {
    icon: Wifi,
    title: "2. Set Interface to Monitor Mode",
    content: (
      <div className="text-sm text-gray-300 space-y-2">
        <p>
          Monitor mode lets the adapter capture all 802.11 frames, not just those
          addressed to it. Use the <strong>Interfaces</strong> tab to switch modes.
        </p>
        <div className="bg-gray-900 rounded p-3 font-mono text-xs space-y-1">
          <div className="text-gray-500"># CLI equivalent</div>
          <div>
            <span className="text-green-400">sudo </span>ifconfig wlan0 down
          </div>
          <div>
            <span className="text-green-400">sudo </span>iwconfig wlan0 mode monitor
          </div>
          <div>
            <span className="text-green-400">sudo </span>ifconfig wlan0 up
          </div>
        </div>
      </div>
    ),
  },
  {
    icon: Radio,
    title: "3. Scan for Access Points",
    content: (
      <div className="text-sm text-gray-300 space-y-2">
        <p>
          The platform scans for 802.11 beacon frames and probe responses, collecting
          BSSID, SSID, channel, signal strength, and encryption type.
        </p>
        <div className="bg-gray-900 rounded p-3 font-mono text-xs space-y-1">
          <div className="text-gray-500"># CLI equivalent</div>
          <div>
            <span className="text-green-400">sudo </span>iwlist wlan0mon scan
          </div>
        </div>
      </div>
    ),
  },
  {
    icon: ShieldAlert,
    title: "4. Discover Connected Clients",
    content: (
      <div className="text-sm text-gray-300 space-y-2">
        <p>
          After selecting a target AP, the platform listens for data frames
          (type 2) addressed to the AP's BSSID to discover connected client MACs.
        </p>
        <div className="bg-gray-900 rounded p-3 font-mono text-xs space-y-1">
          <div className="text-gray-500"># CLI equivalent</div>
          <div>
            <span className="text-green-400">sudo </span>tcpdump -i wlan0mon -e -n{" "}
            <span className="text-yellow-400">'wlan addr3 AA:BB:CC:DD:EE:FF'</span>
          </div>
        </div>
      </div>
    ),
  },
  {
    icon: Zap,
    title: "5. Deauthentication Test",
    content: (
      <div className="text-sm text-gray-300 space-y-2">
        <p>
          Sends IEEE 802.11 deauthentication frames (reason code 7 by default) to
          the target. Use <code className="bg-gray-800 px-1 rounded">ff:ff:ff:ff:ff:ff</code> as
          target MAC to deauth <em>all</em> clients from the AP (broadcast deauth).
        </p>
        <div className="bg-gray-900 rounded p-3 font-mono text-xs space-y-1">
          <div className="text-gray-500"># Scapy equivalent</div>
          <div>
            frame = RadioTap() / Dot11(addr1=<span className="text-yellow-400">TARGET</span>,
            addr2=<span className="text-yellow-400">BSSID</span>, addr3=<span className="text-yellow-400">BSSID</span>)
          </div>
          <div>
            frame = frame / Dot11Deauth(reason=<span className="text-cyan-400">7</span>)
          </div>
          <div>
            sendp(frame, iface=<span className="text-yellow-400">"wlan0mon"</span>, count=<span className="text-cyan-400">100</span>, inter=<span className="text-cyan-400">0.05</span>)
          </div>
        </div>
        <div className="flex items-start gap-2 bg-red-900/30 border border-red-700/50 rounded p-2">
          <AlertTriangle className="w-4 h-4 text-red-400 mt-0.5 shrink-0" />
          <p className="text-xs text-red-300">
            Only test networks you own or have explicit written authorisation to test.
            Unauthorised deauthentication attacks are illegal in most jurisdictions.
          </p>
        </div>
      </div>
    ),
  },
];

function TutorialAccordion() {
  const [open, setOpen] = useState<number | null>(0);
  return (
    <div className="space-y-2">
      {TUTORIAL_STEPS.map((step, i) => {
        const Icon = step.icon;
        const isOpen = open === i;
        return (
          <div
            key={i}
            className="border border-gray-700/60 rounded-lg overflow-hidden"
          >
            <button
              onClick={() => setOpen(isOpen ? null : i)}
              className="w-full flex items-center gap-3 px-4 py-3 bg-gray-800/50 hover:bg-gray-800 transition-colors text-left"
            >
              <Icon className="w-4 h-4 text-cyan-400 shrink-0" />
              <span className="font-medium text-sm text-gray-200 flex-1">
                {step.title}
              </span>
              {isOpen ? (
                <ChevronDown className="w-4 h-4 text-gray-400" />
              ) : (
                <ChevronRight className="w-4 h-4 text-gray-400" />
              )}
            </button>
            {isOpen && <div className="px-4 py-3 bg-gray-900/40">{step.content}</div>}
          </div>
        );
      })}
    </div>
  );
}

// ─── Hardware status banner ───────────────────────────────────────────────────
function HardwareBanner() {
  const { data: status, isLoading, refetch } = useHardwareStatus();

  if (isLoading)
    return (
      <div className="flex items-center gap-2 text-gray-400 text-sm p-4 bg-gray-800/50 rounded-lg">
        <Loader2 className="w-4 h-4 animate-spin" />
        Checking hardware…
      </div>
    );

  if (!status) return null;

  return (
    <div
      className={`rounded-lg border p-4 ${
        status.hardware_ready
          ? "border-green-700/50 bg-green-900/20"
          : "border-yellow-700/50 bg-yellow-900/20"
      }`}
    >
      <div className="flex items-center justify-between mb-3">
        <div className="flex items-center gap-2">
          {status.hardware_ready ? (
            <CheckCircle2 className="w-5 h-5 text-green-400" />
          ) : (
            <AlertTriangle className="w-5 h-5 text-yellow-400" />
          )}
          <span className="font-semibold text-sm">
            {status.hardware_ready ? "Hardware Ready" : "Hardware Not Ready"}
          </span>
          <span className="text-xs text-gray-400">({status.platform})</span>
        </div>
        <button
          onClick={() => refetch()}
          className="text-gray-400 hover:text-gray-200 transition-colors"
        >
          <RefreshCw className="w-4 h-4" />
        </button>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        <div>
          <p className="text-xs text-gray-500 uppercase tracking-wider mb-1">Met</p>
          <ul className="space-y-1">
            {status.requirements_met.map((r) => (
              <li key={r} className="flex items-center gap-2 text-xs text-green-300">
                <CheckCircle2 className="w-3 h-3 shrink-0" />
                {r}
              </li>
            ))}
          </ul>
        </div>
        {status.requirements_missing.length > 0 && (
          <div>
            <p className="text-xs text-gray-500 uppercase tracking-wider mb-1">Missing</p>
            <ul className="space-y-1">
              {status.requirements_missing.map((r) => (
                <li key={r} className="flex items-center gap-2 text-xs text-yellow-300">
                  <XCircle className="w-3 h-3 shrink-0" />
                  {r}
                </li>
              ))}
            </ul>
          </div>
        )}
      </div>
    </div>
  );
}

// ─── Network scanner tab ──────────────────────────────────────────────────────
function NetworkScannerTab() {
  const { data: status } = useHardwareStatus();
  const interfaces = status?.available_interfaces ?? [];
  const [selectedIface, setSelectedIface] = useState("");
  const scan = useScanNetworks();
  const setMode = useSetInterfaceMode();
  const [selectedAp, setSelectedAp] = useState<AccessPoint | null>(null);
  const scanClients = useScanClients();
  const deauth = useDeauth();
  const [targetMac, setTargetMac] = useState("ff:ff:ff:ff:ff:ff");
  const [deauthCount, setDeauthCount] = useState(100);

  return (
    <div className="space-y-4">
      {/* Interface selector */}
      <div className="bg-gray-800/50 rounded-lg p-4 space-y-3">
        <h3 className="text-sm font-semibold text-gray-200">Network Interface</h3>
        <div className="flex flex-wrap gap-2">
          {interfaces.length === 0 ? (
            <p className="text-sm text-gray-400">No WiFi interfaces detected</p>
          ) : (
            interfaces.map((iface) => (
              <button
                key={iface.name}
                onClick={() => setSelectedIface(iface.name)}
                className={`px-3 py-1.5 rounded-lg text-sm border transition-colors ${
                  selectedIface === iface.name
                    ? "border-cyan-500 bg-cyan-900/30 text-cyan-300"
                    : "border-gray-600 bg-gray-700/50 text-gray-300 hover:border-gray-500"
                }`}
              >
                <span className="font-mono">{iface.name}</span>
                {iface.mode && (
                  <span className="ml-1 text-xs text-gray-400">({iface.mode})</span>
                )}
              </button>
            ))
          )}
        </div>
        {selectedIface && (
          <div className="flex gap-2">
            <button
              onClick={() => setMode.mutate({ name: selectedIface, mode: "monitor" })}
              disabled={setMode.isPending}
              className="px-3 py-1.5 text-xs rounded bg-cyan-700/30 border border-cyan-600/50 text-cyan-300 hover:bg-cyan-700/50 transition-colors disabled:opacity-50"
            >
              {setMode.isPending ? (
                <Loader2 className="w-3 h-3 animate-spin inline" />
              ) : null}{" "}
              Set Monitor Mode
            </button>
            <button
              onClick={() => setMode.mutate({ name: selectedIface, mode: "managed" })}
              disabled={setMode.isPending}
              className="px-3 py-1.5 text-xs rounded bg-gray-700/50 border border-gray-600 text-gray-300 hover:bg-gray-700 transition-colors disabled:opacity-50"
            >
              Set Managed Mode
            </button>
          </div>
        )}
      </div>

      {/* Scan button */}
      <button
        disabled={!selectedIface || scan.isPending}
        onClick={() => scan.mutate(selectedIface)}
        className="flex items-center gap-2 px-4 py-2 bg-cyan-600 hover:bg-cyan-500 disabled:opacity-40 disabled:cursor-not-allowed text-white rounded-lg text-sm font-medium transition-colors"
      >
        {scan.isPending ? (
          <Loader2 className="w-4 h-4 animate-spin" />
        ) : (
          <Wifi className="w-4 h-4" />
        )}
        {scan.isPending ? "Scanning…" : "Scan for Access Points"}
      </button>

      {scan.isError && (
        <div className="flex items-center gap-2 p-3 bg-red-900/30 border border-red-700/50 rounded-lg text-red-300 text-sm">
          <AlertTriangle className="w-4 h-4 shrink-0" />
          {(scan.error as Error)?.message}
        </div>
      )}

      {/* AP results */}
      {scan.data && (
        <div className="space-y-2">
          <div className="flex items-center justify-between">
            <h3 className="text-sm font-semibold text-gray-200">
              Access Points ({scan.data.access_points.length})
            </h3>
            {scan.data.note && (
              <span className="text-xs text-gray-500 flex items-center gap-1">
                <Info className="w-3 h-3" />
                {scan.data.note}
              </span>
            )}
          </div>
          <div className="space-y-1 max-h-72 overflow-y-auto">
            {scan.data.access_points.map((ap) => (
              <button
                key={ap.bssid}
                onClick={() => setSelectedAp(ap)}
                className={`w-full text-left px-3 py-2 rounded-lg border transition-colors text-sm ${
                  selectedAp?.bssid === ap.bssid
                    ? "border-cyan-500 bg-cyan-900/20"
                    : "border-gray-700/60 bg-gray-800/30 hover:border-gray-600"
                }`}
              >
                <div className="flex items-center justify-between">
                  <div>
                    <span className="font-medium text-gray-200">{ap.ssid}</span>
                    <span className="ml-2 font-mono text-xs text-gray-400">{ap.bssid}</span>
                  </div>
                  <div className="flex items-center gap-3">
                    {ap.channel && (
                      <span className="text-xs text-gray-400">CH {ap.channel}</span>
                    )}
                    <EncBadge enc={ap.encryption} />
                    <SignalBars dbm={ap.signal_dbm} />
                  </div>
                </div>
              </button>
            ))}
          </div>
        </div>
      )}

      {/* Client scan + deauth */}
      {selectedAp && (
        <div className="border border-gray-700/60 rounded-lg p-4 space-y-4 bg-gray-800/30">
          <h3 className="text-sm font-semibold text-gray-200 flex items-center gap-2">
            <ShieldAlert className="w-4 h-4 text-cyan-400" />
            Target: {selectedAp.ssid}{" "}
            <span className="font-mono text-xs text-gray-400">{selectedAp.bssid}</span>
          </h3>

          <button
            disabled={!selectedIface || scanClients.isPending}
            onClick={() =>
              scanClients.mutate({ iface: selectedIface, bssid: selectedAp.bssid, duration: 10 })
            }
            className="flex items-center gap-2 px-3 py-1.5 bg-gray-700 hover:bg-gray-600 disabled:opacity-40 text-sm rounded-lg transition-colors"
          >
            {scanClients.isPending ? (
              <Loader2 className="w-4 h-4 animate-spin" />
            ) : (
              <Radio className="w-4 h-4" />
            )}
            {scanClients.isPending ? "Listening for clients (10s)…" : "Discover Clients"}
          </button>

          {scanClients.data && (
            <div className="space-y-1">
              <p className="text-xs text-gray-400">
                {scanClients.data.clients.length} client(s) found
              </p>
              {scanClients.data.clients.map((c) => (
                <button
                  key={c.mac}
                  onClick={() => setTargetMac(c.mac)}
                  className={`w-full text-left px-3 py-1.5 rounded border text-xs font-mono transition-colors ${
                    targetMac === c.mac
                      ? "border-cyan-500 bg-cyan-900/20 text-cyan-300"
                      : "border-gray-700 text-gray-300 hover:border-gray-500"
                  }`}
                >
                  {c.mac}
                  {c.signal_dbm != null && (
                    <span className="ml-2 text-gray-500">{c.signal_dbm} dBm</span>
                  )}
                </button>
              ))}
            </div>
          )}

          {/* Deauth controls */}
          <div className="space-y-3 border-t border-gray-700/60 pt-3">
            <h4 className="text-xs font-semibold text-gray-400 uppercase tracking-wider flex items-center gap-1">
              <Zap className="w-3 h-3" /> Deauthentication Test
            </h4>
            <div className="grid grid-cols-2 gap-3">
              <div>
                <label className="text-xs text-gray-400 block mb-1">Target MAC</label>
                <input
                  value={targetMac}
                  onChange={(e) => setTargetMac(e.target.value)}
                  className="w-full bg-gray-900 border border-gray-600 rounded px-2 py-1.5 text-xs font-mono text-gray-200 focus:border-cyan-500 outline-none"
                  placeholder="ff:ff:ff:ff:ff:ff"
                />
              </div>
              <div>
                <label className="text-xs text-gray-400 block mb-1">Packet Count</label>
                <input
                  type="number"
                  min={1}
                  max={10000}
                  value={deauthCount}
                  onChange={(e) => setDeauthCount(Number(e.target.value))}
                  className="w-full bg-gray-900 border border-gray-600 rounded px-2 py-1.5 text-xs font-mono text-gray-200 focus:border-cyan-500 outline-none"
                />
              </div>
            </div>

            <button
              disabled={!selectedIface || deauth.isPending}
              onClick={() =>
                deauth.mutate({
                  interface: selectedIface,
                  gateway_mac: selectedAp.bssid,
                  target_mac: targetMac,
                  count: deauthCount,
                  reason_code: 7,
                })
              }
              className="flex items-center gap-2 px-4 py-2 bg-red-700 hover:bg-red-600 disabled:opacity-40 text-white rounded-lg text-sm font-medium transition-colors w-full justify-center"
            >
              {deauth.isPending ? (
                <Loader2 className="w-4 h-4 animate-spin" />
              ) : (
                <Zap className="w-4 h-4" />
              )}
              {deauth.isPending ? "Sending deauth frames…" : "Send Deauth Frames"}
            </button>

            {deauth.data && (
              <div className="flex items-center gap-2 p-2 bg-green-900/30 border border-green-700/50 rounded text-green-300 text-xs">
                <CheckCircle2 className="w-3 h-3" />
                {deauth.data.message}
              </div>
            )}
            {deauth.isError && (
              <div className="flex items-center gap-2 p-2 bg-red-900/30 border border-red-700/50 rounded text-red-300 text-xs">
                <AlertTriangle className="w-3 h-3" />
                {(deauth.error as Error)?.message}
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
}

// ─── Main page ────────────────────────────────────────────────────────────────
type Tab = "tutorial" | "scanner";

export default function WirelessAuditorPage() {
  const [tab, setTab] = useState<Tab>("tutorial");

  return (
    <div className="p-6 max-w-5xl mx-auto space-y-6">
      {/* Header */}
      <div className="flex items-center gap-3">
        <div className="p-2 bg-cyan-500/10 rounded-lg">
          <Wifi className="w-6 h-6 text-cyan-400" />
        </div>
        <div>
          <h1 className="text-xl font-bold text-gray-100">Wireless Auditor</h1>
          <p className="text-sm text-gray-400">
            802.11 network analysis, client discovery &amp; deauthentication testing
          </p>
        </div>
        <div className="ml-auto flex items-center gap-2 px-3 py-1 bg-red-900/30 border border-red-700/50 rounded-lg">
          <AlertTriangle className="w-4 h-4 text-red-400" />
          <span className="text-xs text-red-300 font-medium">Authorised use only</span>
        </div>
      </div>

      {/* Hardware status */}
      <HardwareBanner />

      {/* Tabs */}
      <div className="flex gap-1 bg-gray-800/50 rounded-lg p-1 w-fit">
        {(["tutorial", "scanner"] as Tab[]).map((t) => (
          <button
            key={t}
            onClick={() => setTab(t)}
            className={`px-4 py-1.5 rounded-md text-sm font-medium transition-colors capitalize ${
              tab === t
                ? "bg-gray-700 text-gray-100"
                : "text-gray-400 hover:text-gray-200"
            }`}
          >
            {t}
          </button>
        ))}
      </div>

      {/* Tab content */}
      {tab === "tutorial" ? <TutorialAccordion /> : <NetworkScannerTab />}
    </div>
  );
}
