import { memo } from "react";
import { type NodeProps } from "reactflow";
import { Globe, Code2, Gamepad2, Palette, Briefcase, MessageSquare } from "lucide-react";
import { BaseNode } from "./BaseNode";
import type { OsintNodeData } from "../../types";

const CATEGORY_ICONS: Record<string, React.ReactNode> = {
  social: <Globe className="h-4 w-4" style={{ color: "var(--node-social-profile, #f0abfc)" }} />,
  developer: <Code2 className="h-4 w-4" style={{ color: "var(--node-social-profile, #f0abfc)" }} />,
  gaming: <Gamepad2 className="h-4 w-4" style={{ color: "var(--node-social-profile, #f0abfc)" }} />,
  creative: <Palette className="h-4 w-4" style={{ color: "var(--node-social-profile, #f0abfc)" }} />,
  professional: <Briefcase className="h-4 w-4" style={{ color: "var(--node-social-profile, #f0abfc)" }} />,
  forum: <MessageSquare className="h-4 w-4" style={{ color: "var(--node-social-profile, #f0abfc)" }} />,
};

const DEFAULT_ICON = <Globe className="h-4 w-4" style={{ color: "var(--node-social-profile, #f0abfc)" }} />;

export const SocialProfileNode = memo(function SocialProfileNode(props: NodeProps<OsintNodeData>) {
  const category = String(props.data.properties?.category ?? "social");
  const icon = CATEGORY_ICONS[category] ?? DEFAULT_ICON;
  return <BaseNode icon={icon} nodeProps={props} />;
});
