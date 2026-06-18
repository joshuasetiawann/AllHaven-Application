// Request payload types for the settings & AI provider endpoints.
// (Shared response types live in "@/types".)

export type {
  Integration,
  AiProvider,
  FieldSpec,
  SecretPreview,
  IntegrationStatusValue,
} from "@/types";

export interface IntegrationUpdatePayload {
  public_config: Record<string, string>;
  secrets: Record<string, string>;
}

export interface AiProviderUpdatePayload {
  public_config?: Record<string, string>;
  secrets?: Record<string, string>;
  default_model?: string | null;
  privacy_mode?: string | null;
  system_prompt?: string | null;
  temperature?: number | null;
  enabled?: boolean | null;
}

export type PrivacyMode = "local_private" | "external_allowed" | "manual_provider";

export interface GoogleScopeGroup {
  id: string;
  label: string;
  scopes: string[];
  sensitive: boolean;
  default: boolean;
  note: string;
}

export interface GoogleScopes {
  default_scopes: string[];
  catalog: GoogleScopeGroup[];
  notes: string[];
}
