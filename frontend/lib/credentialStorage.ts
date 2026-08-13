import { Capacitor } from "@capacitor/core";

type StringStorage = {
  getItem: (key: string) => Promise<string | null>;
  setItem: (key: string, value: string) => Promise<void>;
  removeItem: (key: string) => Promise<void>;
};

let preferencesPromise: Promise<StringStorage> | null = null;
let secureStoragePromise: Promise<StringStorage> | null = null;

// Preferences remains the browser implementation so existing web behavior and
// storage keys do not change. On native platforms it is used only to migrate and
// remove credentials written by older AllHaven releases.
function preferencesStorage(): Promise<StringStorage> {
  if (!preferencesPromise) {
    preferencesPromise = import("@capacitor/preferences").then(({ Preferences }) => ({
      getItem: async (key) => (await Preferences.get({ key })).value,
      setItem: async (key, value) => Preferences.set({ key, value }),
      removeItem: async (key) => Preferences.remove({ key }),
    }));
  }
  return preferencesPromise;
}

function nativeSecureStorage(): Promise<StringStorage> {
  if (!secureStoragePromise) {
    secureStoragePromise = import("@aparajita/capacitor-secure-storage").then(
      async ({ KeychainAccess, SecureStorage }) => {
        // Keep credentials local to this device and available only after unlock.
        // These settings are no-ops on Android, where values are encrypted with
        // an AES-GCM key held by Android Keystore.
        await SecureStorage.setSynchronize(false);
        await SecureStorage.setDefaultKeychainAccess(KeychainAccess.whenUnlockedThisDeviceOnly);
        await SecureStorage.setKeyPrefix("allhaven_secure_");

        // Return a plain object instead of the Capacitor proxy. Plugin proxies
        // expose a `then` trap and must not be returned directly from a Promise.
        return {
          getItem: SecureStorage.getItem.bind(SecureStorage),
          setItem: SecureStorage.setItem.bind(SecureStorage),
          removeItem: SecureStorage.removeItem.bind(SecureStorage),
        };
      },
    );
  }
  return secureStoragePromise;
}

async function getItem(key: string): Promise<string | null> {
  const legacy = await preferencesStorage();
  if (!Capacitor.isNativePlatform()) return legacy.getItem(key);

  let secure: StringStorage;
  let value: string | null;
  try {
    secure = await nativeSecureStorage();
    value = await secure.getItem(key);
  } catch (error) {
    // Never retain a plaintext credential merely because the secure vault is
    // unavailable. This signs the user out, which is safer than falling back.
    await legacy.removeItem(key);
    throw error;
  }
  if (value !== null) {
    // A previous migration may have written securely but failed before cleanup.
    await legacy.removeItem(key);
    return value;
  }

  const legacyValue = await legacy.getItem(key);
  if (legacyValue === null) return null;

  // Write first, then delete the plaintext legacy value. If the secure write
  // fails, do not silently continue persisting credentials in Preferences.
  await secure.setItem(key, legacyValue);
  await legacy.removeItem(key);
  return legacyValue;
}

async function setItem(key: string, value: string): Promise<void> {
  const legacy = await preferencesStorage();
  if (!Capacitor.isNativePlatform()) {
    await legacy.setItem(key, value);
    return;
  }

  try {
    const secure = await nativeSecureStorage();
    await secure.setItem(key, value);
  } catch (error) {
    await legacy.removeItem(key);
    throw error;
  }
  await legacy.removeItem(key);
}

async function removeItem(key: string): Promise<void> {
  const legacy = await preferencesStorage();
  if (!Capacitor.isNativePlatform()) {
    await legacy.removeItem(key);
    return;
  }

  // Logout must attempt both stores even if one native operation fails.
  let firstError: unknown;
  try {
    const secure = await nativeSecureStorage();
    await secure.removeItem(key);
  } catch (error) {
    firstError = error;
  }

  try {
    await legacy.removeItem(key);
  } catch (error) {
    firstError ??= error;
  }

  if (firstError !== undefined) throw firstError;
}

/**
 * String storage for authentication credentials.
 *
 * Native: iOS Keychain / Android Keystore-backed encrypted storage.
 * Browser: Capacitor Preferences, preserving the existing web behavior.
 */
export const credentialStorage: StringStorage = { getItem, setItem, removeItem };
