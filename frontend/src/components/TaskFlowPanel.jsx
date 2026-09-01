import React from "react";
import { Box, Flex, Loader, Text } from "@mantine/core";
import { IconCheck } from "@tabler/icons-react";

const VALID_STATUSES = new Set(["pending", "in_progress", "done"]);

const normalizePlanSteps = (context) => {
  const rawSteps = Array.isArray(context?.plan_steps) ? context.plan_steps : [];
  const currentIndex = Number.isInteger(context?.plan_current_index)
    ? context.plan_current_index
    : 0;
  const planStatus = context?.plan_status;

  return rawSteps.map((step, index) => {
    const title =
      (typeof step?.title === "string" && step.title.trim()) ||
      `Step ${index + 1}`;
    let status = typeof step?.status === "string" ? step.status : null;

    if (planStatus === "completed") {
      status = "done";
    } else if (!status) {
      if (planStatus === "completed" || index < currentIndex) {
        status = "done";
      } else if (index === currentIndex) {
        status = "in_progress";
      } else {
        status = "pending";
      }
    }

    if (!VALID_STATUSES.has(status)) {
      status = "pending";
    }

    return {
      index: index + 1,
      title,
      status,
    };
  });
};

const StepIndicator = ({ status }) => {
  const containerStyle = {
    width: 12,
    height: 12,
    display: "flex",
    alignItems: "center",
    justifyContent: "center",
    flexShrink: 0,
  };

  if (status === "done") {
    return (
      <Box style={containerStyle}>
        <IconCheck size={10} stroke={2.5} color="#495057" />
      </Box>
    );
  }

  if (status === "in_progress") {
    return (
      <Box style={containerStyle}>
        <Loader size={10} color="#495057" />
      </Box>
    );
  }

  return (
    <Box
      style={{
        ...containerStyle,
        width: 10,
        height: 10,
        borderRadius: "50%",
        border: "1.5px solid #495057",
        backgroundColor: "#fff",
      }}
    />
  );
};

const TaskFlowPanel = ({ context }) => {
  const steps = React.useMemo(() => normalizePlanSteps(context), [context]);

  if (steps.length === 0) {
    return null;
  }

  return (
    <Box
      px="md"
      py="sm"
      style={{
        margin: "0 12px 10px 12px",
        border: "1px solid rgba(111, 134, 133, 0.14)",
        borderRadius: 16,
        background:
          "linear-gradient(180deg, rgba(246,248,248,0.96) 0%, rgba(241,245,244,0.92) 100%)",
      }}
    >
      <Flex align="center" mb={8}>
        <Text size="xs" fw={700} c="#687877" tt="uppercase" style={{ letterSpacing: "0.07em" }}>
          Task Flow
        </Text>
      </Flex>
      <Flex direction="column" gap={6}>
        {steps.map((step) => (
          <Flex key={`${step.index}-${step.title}`} align="flex-start" gap={8}>
            <Flex align="center" gap={8} style={{ minWidth: 0 }}>
              <StepIndicator status={step.status} />
              <Text size="xs" c="#617170" style={{ minWidth: 0, lineHeight: 1.35 }}>
                {step.index}. {step.title}
              </Text>
            </Flex>
          </Flex>
        ))}
      </Flex>
    </Box>
  );
};

export default TaskFlowPanel;
