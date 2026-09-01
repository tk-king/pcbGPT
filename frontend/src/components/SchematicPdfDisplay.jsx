import { memo } from "react";
import { Box, Text } from "@mantine/core";

const SchematicPdfDisplay = memo(({ pdfSrc }) => {

  if (!pdfSrc) {
    return (
      <Box
        p="md"
        style={{
          height: "100%",
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          background:
            "linear-gradient(180deg, rgba(250,252,252,0.78) 0%, rgba(246,249,248,0.92) 100%)",
        }}
      >
        <Box
          style={{
            border: "1px solid rgba(111, 134, 133, 0.14)",
            borderRadius: 16,
            backgroundColor: "rgba(255,255,255,0.82)",
            padding: "24px 28px",
          }}
        >
          <Text color="dimmed">No schematic PDF available yet.</Text>
        </Box>
      </Box>
    );
  }

  return (
    <Box w="100%" h="100%" p="md" style={{ background:
      "linear-gradient(180deg, rgba(250,252,252,0.78) 0%, rgba(246,249,248,0.92) 100%)" }}>
      <Box
        style={{
          height: "100%",
          border: "1px solid rgba(111, 134, 133, 0.14)",
          borderRadius: 16,
          overflow: "hidden",
          backgroundColor: "rgba(255,255,255,0.82)",
          boxShadow: "0 10px 30px rgba(30, 49, 48, 0.05)",
        }}
      >
        <Box
          component="iframe"
          src={pdfSrc}
          title="Schematic PDF"
          style={{
            width: "100%",
            height: "100%",
            border: 0,
            backgroundColor: "#ffffff",
          }}
        />
      </Box>
    </Box>
  );
  });
  
  export default SchematicPdfDisplay;
