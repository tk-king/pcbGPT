// Merges cumulative usage counters from successive metrics events.

export const mergeMetrics = (prevMetrics, nextMetrics) => {
  if (!nextMetrics?.usage) return prevMetrics;
  if (!prevMetrics?.usage) return nextMetrics;
  return {
    ...nextMetrics,
    usage: {
      ...nextMetrics.usage,
      requests: (prevMetrics.usage.requests || 0) + (nextMetrics.usage.requests || 0),
      input_tokens: (prevMetrics.usage.input_tokens || 0) + (nextMetrics.usage.input_tokens || 0),
      output_tokens: (prevMetrics.usage.output_tokens || 0) + (nextMetrics.usage.output_tokens || 0),
      total_tokens: (prevMetrics.usage.total_tokens || 0) + (nextMetrics.usage.total_tokens || 0),
      max_total_tokens: Math.max(
        prevMetrics.usage.max_total_tokens || 0,
        nextMetrics.usage.max_total_tokens || 0,
      ),
    },
  };
};
