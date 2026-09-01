import { Button } from "@mantine/core";
import { IconDownload } from "@tabler/icons-react";

// Small filled download button used for netlist / project downloads.
const DownloadButton = ({ href, children, ...props }) => (
  <Button
    size="xs"
    variant="filled"
    color="brand"
    component="a"
    href={href}
    target="_blank"
    rel="noopener noreferrer"
    disabled={!href}
    leftSection={<IconDownload size={14} />}
    style={{ flexShrink: 0 }}
    {...props}
  >
    {children}
  </Button>
);

export default DownloadButton;
