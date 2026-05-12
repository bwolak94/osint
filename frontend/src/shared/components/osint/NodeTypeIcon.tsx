import {
  User,
  Building2,
  Mail,
  Phone,
  AtSign,
  Globe,
  Wifi,
  Share2,
} from "lucide-react";

const nodeConfig: Record<string, { icon: typeof User; color: string }> = {
  person: { icon: User, color: "var(--node-person)" },
  company: { icon: Building2, color: "var(--node-company)" },
  email: { icon: Mail, color: "var(--node-email)" },
  phone: { icon: Phone, color: "var(--node-phone)" },
  username: { icon: AtSign, color: "var(--node-username)" },
  ip: { icon: Wifi, color: "var(--node-ip)" },
  domain: { icon: Globe, color: "var(--node-domain)" },
  social_profile: { icon: Share2, color: "var(--node-social-profile, #f0abfc)" },
};

interface NodeTypeIconProps {
  type: string;
  size?: "sm" | "md" | "lg";
}

const sizes = { sm: "h-4 w-4", md: "h-5 w-5", lg: "h-6 w-6" };

const PERSON_CONFIG = { icon: User, color: "var(--node-person)" };

export function NodeTypeIcon({ type, size = "md" }: NodeTypeIconProps) {
  const config = nodeConfig[type] ?? PERSON_CONFIG;
  const Icon = config.icon;
  return <Icon className={sizes[size]} style={{ color: config.color }} />;
}
