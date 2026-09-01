import React from "react";
import { useDebouncedValue } from "@mantine/hooks";
import { getPartIndexStatus, searchParts } from "../api/parts.js";

export const PAGE_SIZE = 25;
const EMPTY_PAYLOAD = {
  results: [],
  total: 0,
  page: 1,
  page_size: PAGE_SIZE,
};

const normalizePartsPayload = (payload) => {
  const results = Array.isArray(payload?.results)
    ? payload.results
    : Array.isArray(payload?.items)
      ? payload.items
      : Array.isArray(payload?.parts)
        ? payload.parts
        : [];
  const totalValue = payload?.total ?? payload?.count ?? results.length;
  const pageValue = payload?.page ?? 1;
  const pageSizeValue = payload?.page_size ?? payload?.pageSize ?? PAGE_SIZE;
  return {
    results,
    total: Number(totalValue) || 0,
    page: Number(pageValue) || 1,
    page_size: Number(pageSizeValue) || PAGE_SIZE,
  };
};

// Search / pagination / selection state for the parts browser.
const usePartsSearch = ({ opened, onPartIndexStatusChange }) => {
  const [query, setQuery] = React.useState("");
  const [page, setPage] = React.useState(1);
  const [payload, setPayload] = React.useState(EMPTY_PAYLOAD);
  const [selectedKey, setSelectedKey] = React.useState(null);
  const [loading, setLoading] = React.useState(false);
  const [error, setError] = React.useState("");
  const [reloadNonce, setReloadNonce] = React.useState(0);
  const [partIndexStatus, setPartIndexStatus] = React.useState(null);
  const [debouncedQuery] = useDebouncedValue(query, 250);

  React.useEffect(() => {
    if (!opened) return;
    let cancelled = false;
    const loadStatus = async () => {
      try {
        const data = await getPartIndexStatus();
        if (cancelled) return;
        setPartIndexStatus(data);
        onPartIndexStatusChange?.(data);
      } catch {
        // ignore
      }
    };
    loadStatus();
    return () => { cancelled = true; };
  }, [opened, onPartIndexStatusChange]);

  React.useEffect(() => {
    if (!opened) {
      return;
    }
    let cancelled = false;
    const load = async () => {
      setLoading(true);
      setError("");
      try {
        const nextPayload = await searchParts({
          query: debouncedQuery,
          page,
          pageSize: PAGE_SIZE,
        });
        if (cancelled) {
          return;
        }
        setPayload(normalizePartsPayload(nextPayload));
      } catch (nextError) {
        if (cancelled) {
          return;
        }
        setError(nextError?.message || "Failed to load parts.");
        setPayload({ ...EMPTY_PAYLOAD, page });
      } finally {
        if (!cancelled) {
          setLoading(false);
        }
      }
    };
    load();
    return () => {
      cancelled = true;
    };
  }, [debouncedQuery, opened, page, reloadNonce]);

  React.useEffect(() => {
    setPage(1);
  }, [debouncedQuery]);

  React.useEffect(() => {
    const results = payload?.results || [];
    if (results.length === 0) {
      setSelectedKey(null);
      return;
    }
    const hasSelected = results.some((part) => part.key === selectedKey);
    if (!hasSelected) {
      setSelectedKey(results[0].key);
    }
  }, [payload, selectedKey]);

  const results = payload?.results || [];
  const total = Number(payload?.total || 0);
  const pageCount = Math.max(1, Math.ceil(total / PAGE_SIZE));
  const selectedPart = results.find((part) => part.key === selectedKey) || null;

  const defaultAccordionValues = React.useMemo(() => {
    if (!selectedPart) {
      return [];
    }
    const nextValues = [];
    if ((selectedPart.footprints || []).length <= 4) {
      nextValues.push("footprints");
    }
    if ((selectedPart.pins || []).length <= 10) {
      nextValues.push("pins");
    }
    return nextValues;
  }, [selectedPart]);

  const refreshPartIndexStatus = React.useCallback(async () => {
    const data = await getPartIndexStatus();
    setPartIndexStatus(data);
    onPartIndexStatusChange?.(data);
    return data;
  }, [onPartIndexStatusChange]);

  const bumpReload = React.useCallback(() => {
    setReloadNonce((current) => current + 1);
  }, []);

  const focusOnPart = React.useCallback(({ name, key }) => {
    if (name) setQuery(name);
    if (key !== undefined) setSelectedKey(key);
    setPage(1);
  }, []);

  return {
    query,
    setQuery,
    debouncedQuery,
    page: Math.min(page, pageCount),
    pageCount,
    setPage,
    results,
    total,
    selectedKey,
    setSelectedKey,
    selectedPart,
    defaultAccordionValues,
    loading,
    error,
    partIndexStatus,
    refreshPartIndexStatus,
    bumpReload,
    focusOnPart,
  };
};

export default usePartsSearch;
