import JSZip from "jszip";

const arrayBufferToBase64 = (buffer) => {
  const bytes = new Uint8Array(buffer);
  let binary = "";
  const chunkSize = 0x8000;
  for (let i = 0; i < bytes.byteLength; i += chunkSize) {
    binary += String.fromCharCode(...bytes.subarray(i, i + chunkSize));
  }
  return btoa(binary);
};

const normalizeZipPath = (zipPath, projectName) => {
  const segments = zipPath.split("/").filter(Boolean);
  if (segments.length > 1 && projectName && segments[0] === projectName) {
    segments.shift();
  }
  return segments.join("/");
};

const ensureFileHandle = async (rootHandle, relativePath) => {
  const segments = relativePath.split("/").filter(Boolean);
  let dirHandle = rootHandle;
  for (let i = 0; i < segments.length - 1; i += 1) {
    dirHandle = await dirHandle.getDirectoryHandle(segments[i], { create: true });
  }
  const fileName = segments[segments.length - 1];
  return dirHandle.getFileHandle(fileName, { create: true });
};

const addDirectoryToZip = async (zip, dirHandle, prefix = "") => {
  for await (const entry of dirHandle.values()) {
    if (entry.kind === "file") {
      const file = await entry.getFile();
      const relativeName = `${prefix}${file.name}`;
      zip.file(relativeName, file);
    } else if (entry.kind === "directory") {
      const nextPrefix = `${prefix}${entry.name}/`;
      const subFolder = zip.folder(nextPrefix) || zip;
      await addDirectoryToZip(subFolder, entry, "");
    }
  }
};

const pickWithInputFallback = () =>
  new Promise((resolve, reject) => {
    const input = document.createElement("input");
    let settled = false;
    let opened = false;
    const settle = (fn, value) => {
      if (settled) return;
      settled = true;
      window.removeEventListener("focus", handleWindowFocus);
      fn(value);
    };
    const handleWindowFocus = () => {
      if (!opened || settled) return;
      window.setTimeout(() => {
        if (!settled && (!input.files || input.files.length === 0)) {
          settle(reject, new Error("Folder selection cancelled."));
        }
      }, 300);
    };
    input.type = "file";
    input.webkitdirectory = true;
    input.multiple = true;
    input.oncancel = () => settle(reject, new Error("Folder selection cancelled."));
    input.onchange = async (event) => {
      try {
        const files = Array.from(event.target.files || []);
        if (!files.length) {
          settle(reject, new Error("No files selected."));
          return;
        }
        const zip = new JSZip();
        let folderName = null;
        files.forEach((file) => {
          const rel = file.webkitRelativePath || file.name;
          if (!folderName && file.webkitRelativePath) {
            folderName = file.webkitRelativePath.split("/")[0] || "project";
          }
          zip.file(rel, file);
        });
        const buffer = await zip.generateAsync({ type: "arraybuffer" });
        settle(resolve, {
          archiveBase64: arrayBufferToBase64(buffer),
          folderName: folderName || "project",
          handle: null,
          usedPicker: false,
        });
      } catch (err) {
        settle(reject, err);
      }
    };
    window.addEventListener("focus", handleWindowFocus);
    window.setTimeout(() => {
      opened = true;
    }, 0);
    input.click();
  });

export const pickNativeDirectory = async () => {
  const api = window.pywebview?.api;
  if (!api?.choose_folder) return null;
  const result = await api.choose_folder();
  if (!result || result.cancelled || !result.path) {
    throw new Error("Folder selection cancelled.");
  }
  const path = result.path;
  return {
    folderPath: path,
    folderName: path.split(/[\\/]/).filter(Boolean).pop() || "project",
  };
};

export const pickDirectoryAsArchive = async () => {
  if (window.showDirectoryPicker) {
    const handle = await window.showDirectoryPicker();
    // Proactively request readwrite; browsers may otherwise defer/deny writes.
    try {
      await handle.requestPermission({ mode: "readwrite" });
    } catch (e) {
      // best-effort; caller can retry
      console.warn("requestPermission failed", e);
    }
    const { archiveBase64, folderName } = await archiveFromHandle(handle);
    return { archiveBase64, folderName, handle, usedPicker: true };
  }
  return pickWithInputFallback();
};

export const archiveFromHandle = async (handle) => {
  const zip = new JSZip();
  await addDirectoryToZip(zip, handle);
  const buffer = await zip.generateAsync({ type: "arraybuffer" });
  return { archiveBase64: arrayBufferToBase64(buffer), folderName: handle.name };
};

export const writeZipToDirectory = async ({ zipBuffer, directoryHandle, projectName }) => {
  const zip = await JSZip.loadAsync(zipBuffer);
  for (const [zipPath, entry] of Object.entries(zip.files)) {
    if (entry.dir) continue;
    const relativePath = normalizeZipPath(zipPath, projectName);
    const fileData = await entry.async("uint8array");
    const fileHandle = await ensureFileHandle(directoryHandle, relativePath);
    const writable = await fileHandle.createWritable();
    await writable.write(fileData);
    await writable.close();
  }
};

export const triggerDownloadFromBuffer = (buffer, filename) => {
  const blob = new Blob([buffer], { type: "application/zip" });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  a.style.display = "none";
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
  URL.revokeObjectURL(url);
};

export const isFileSystemAPISupported = () => Boolean(window.showDirectoryPicker);
export const isNativeDirectoryPickerSupported = () =>
  Boolean(window.pywebview?.api?.choose_folder);
export const isDirectoryHandle = (handle) =>
  Boolean(handle && handle.kind === "directory" && typeof handle.values === "function");

const DB_NAME = "pcbgpt_sync_handles";
const STORE_NAME = "dir_handles";
const DB_VERSION = 1;

const openHandleDb = () =>
  new Promise((resolve, reject) => {
    if (!("indexedDB" in window)) {
      reject(new Error("IndexedDB is not available."));
      return;
    }
    const request = indexedDB.open(DB_NAME, DB_VERSION);
    request.onupgradeneeded = () => {
      const db = request.result;
      if (!db.objectStoreNames.contains(STORE_NAME)) {
        db.createObjectStore(STORE_NAME);
      }
    };
    request.onsuccess = () => resolve(request.result);
    request.onerror = () => reject(request.error);
  });

const withStore = async (mode, fn) => {
  const db = await openHandleDb();
  return new Promise((resolve, reject) => {
    const tx = db.transaction(STORE_NAME, mode);
    const store = tx.objectStore(STORE_NAME);
    let request;
    try {
      request = fn(store);
    } catch (err) {
      reject(err);
      return;
    }

    const isRequest =
      request &&
      typeof request === "object" &&
      "onsuccess" in request &&
      "onerror" in request;

    let txDone = false;
    let requestDone = !isRequest;
    let requestResult = isRequest ? undefined : request;
    let settled = false;

    const maybeResolve = () => {
      if (!settled && txDone && requestDone) {
        settled = true;
        resolve(requestResult);
      }
    };

    const rejectOnce = (error) => {
      if (!settled) {
        settled = true;
        reject(error || new Error("IndexedDB transaction failed."));
      }
    };

    if (isRequest) {
      request.onsuccess = () => {
        requestResult = request.result;
        requestDone = true;
        maybeResolve();
      };
      request.onerror = () => rejectOnce(request.error || tx.error);
    }

    tx.oncomplete = () => {
      txDone = true;
      maybeResolve();
    };
    tx.onerror = () => rejectOnce(tx.error);
    tx.onabort = () => rejectOnce(tx.error);
  }).finally(() => db.close());
};

export const storeDirectoryHandle = async (sessionId, handle) => {
  if (!sessionId || !isDirectoryHandle(handle)) return false;
  await withStore("readwrite", (store) => store.put(handle, sessionId));
  return true;
};

export const loadDirectoryHandle = async (sessionId) => {
  if (!sessionId) return null;
  try {
    const handle = await withStore("readonly", (store) => store.get(sessionId));
    if (handle && !isDirectoryHandle(handle)) {
      console.warn("Stored value is not a valid FileSystemDirectoryHandle.");
      return null;
    }
    return handle || null;
  } catch (err) {
    console.warn("Failed to load directory handle:", err);
    return null;
  }
};

export const deleteDirectoryHandle = async (sessionId) => {
  if (!sessionId) return false;
  try {
    await withStore("readwrite", (store) => store.delete(sessionId));
    return true;
  } catch (err) {
    console.warn("Failed to delete directory handle:", err);
    return false;
  }
};
