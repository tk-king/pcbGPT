import { memo } from "react";
import { Box, Text } from "@mantine/core";

const InfoMessage = memo(({ info }) => (
  <Box py="xs" style={{ display: "flex", justifyContent: "center", width: "100%" }}>
    <Box
      px="md"
      py={7}
      style={{
        borderRadius: 999,
        border: "1px solid rgba(111, 134, 133, 0.16)",
        background:
          "linear-gradient(180deg, rgba(246,248,248,0.98) 0%, rgba(240,244,243,0.94) 100%)",
        boxShadow: "0 6px 20px rgba(30, 49, 48, 0.04)",
        maxWidth: "100%",
      }}
    >
      <Text
        size="xs"
        c="#6d7c7b"
        ta="center"
        style={{ whiteSpace: "nowrap" }}
      >
        {info}
      </Text>
    </Box>
  </Box>
));

export default InfoMessage;
