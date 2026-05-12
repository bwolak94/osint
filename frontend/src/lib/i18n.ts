/**
 * i18next configuration — bilingual EN/PL with lazy namespace loading.
 *
 * Language detection order:
 *   1. i18next cookie (set on language switch)
 *   2. Browser Accept-Language header
 *   3. Default: "en"
 *
 * Namespaces are loaded lazily — calendar.json is NOT loaded on the news page.
 * Polish has 4 plural forms; use i18next built-in plural rules (not custom logic).
 */

import i18n from "i18next";
import LanguageDetector from "i18next-browser-languagedetector";
import HttpBackend from "i18next-http-backend";
import { initReactI18next } from "react-i18next";

export const SUPPORTED_LANGUAGES = ["en", "pl"] as const;
export type SupportedLanguage = (typeof SUPPORTED_LANGUAGES)[number];

export const NAMESPACES = [
  "common",
  "news",
  "calendar",
  "tasks",
  "knowledge",
  "chat",
] as const;
export type Namespace = (typeof NAMESPACES)[number];

i18n
  .use(HttpBackend)
  .use(LanguageDetector)
  .use(initReactI18next)
  .init({
    fallbackLng: "en",
    supportedLngs: SUPPORTED_LANGUAGES,

    // Lazy-load namespaces — only "common" loaded on every page
    ns: NAMESPACES,
    defaultNS: "common",

    backend: {
      loadPath: "/locales/{{lng}}/{{ns}}.json",
    },

    detection: {
      // Cookie → browser language → default
      order: ["cookie", "navigator"],
      caches: ["cookie"],
      cookieMinutes: 525_600, // 1 year
    },

    interpolation: {
      // React already escapes — no double-escaping needed
      escapeValue: false,
    },

    // Reduce console noise in production
    debug: import.meta.env.DEV,
  });

export default i18n;
